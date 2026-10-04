from dataclasses import asdict, dataclass
import datetime
import json
import logging
import os
import time
from typing import Dict, List, Optional, Set
import docker

# Configure English system logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s"
)


@dataclass
class TaskConfig:
  name: str
  path: str
  requirements: List[str]


@dataclass
class CrashReport:
  timestamp: str
  task_name: str
  script_path: str
  container_id: str
  exit_code: Optional[int]
  oom_killed: bool
  stdout: str
  stderr: str
  restart_count: int


class UnifiedSandboxSupervisor:

  def __init__(
      self,
      config_path: str = "config.json",
      crash_log_file: str = "crash_reports.json",
      docker_image: str = "python:3.11-slim",
      check_interval_seconds: int = 300,  # 5 minutes check cycle
      max_retries: int = 3,
      cpu_quota: float = 0.05,  # 5% of 1 CPU core
      mem_limit: str = "500m",  # 500 MB RAM limit
  ):
    self.client = docker.from_env()
    self.config_path = os.path.abspath(config_path)
    self.crash_log_file = os.path.abspath(crash_log_file)
    self.docker_image = docker_image
    self.check_interval_seconds = check_interval_seconds
    self.max_retries = max_retries
    self.nano_cpus = int(cpu_quota * 1_000_000_000)
    self.mem_limit = mem_limit

    self.retry_counters: Dict[str, int] = {}
    self.permanently_stopped_tasks: Set[str] = set()

  def load_configs(self) -> List[TaskConfig]:
    """Read task configurations dynamically from config.json."""
    if not os.path.exists(self.config_path):
      logging.error(f"Config file not found: {self.config_path}")
      return []

    try:
      with open(self.config_path, "r", encoding="utf-8") as f:
        data = json.load(f)
      return [
          TaskConfig(
              name=item.get("name", "Unnamed"),
              path=item.get("path", ""),
              requirements=item.get("requirements", []),
          )
          for item in data
      ]
    except Exception as e:
      logging.error(f"Error reading JSON config file: {e}")
      return []

  def launch_task(self, task: TaskConfig):
    """Launch a single task inside an isolated, resource-constrained container."""
    abs_script_path = os.path.abspath(task.path)
    if not os.path.exists(abs_script_path):
      logging.error(
          f"Script path not found for task '{task.name}': {abs_script_path}"
      )
      return

    script_filename = os.path.basename(abs_script_path)

    # Command to install requirements and run Python script with unbuffered stdout (-u)
    install_cmd = ""
    if task.requirements:
      reqs_str = " ".join(task.requirements)
      install_cmd = f"pip install --no-cache-dir --user {reqs_str} && "

    cmd = f"/bin/sh -c '{install_cmd}python -u /sandbox/{script_filename}'"

    labels = {
        "managed_by": "script_runner",
        "task_name": task.name,
        "script_path": task.path,
    }

    # Environment variables to support non-root pip installation & live stdout
    env_vars = {
        "HOME": "/tmp",
        "PATH": (
            "/tmp/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
        ),
        "PYTHONPATH": "/tmp/.local/lib/python3.11/site-packages",
        "PYTHONUNBUFFERED": "1",
    }

    try:
      container = self.client.containers.run(
          image=self.docker_image,
          command=cmd,
          environment=env_vars,
          volumes={
              abs_script_path: {
                  "bind": f"/sandbox/{script_filename}",
                  "mode": "ro",  # Read-only bind mount for isolation
              }
          },
          working_dir="/sandbox",
          mem_limit=self.mem_limit,
          nano_cpus=self.nano_cpus,
          network_disabled=False,
          labels=labels,
          detach=True,
          user="1000:1000",  # Non-root user execution
          security_opt=["no-new-privileges:true"],
      )
      logging.info(
          f"🚀 Task '{task.name}' launched in container: {container.short_id}"
      )
    except Exception as e:
      logging.error(f"Failed to launch container for task '{task.name}': {e}")

  def sync_tasks(self):
      """Detect newly added or missing tasks in config.json and launch them."""
      tasks = self.load_configs()
      logging.info(
          f"📋 Found {len(tasks)} task(s) in config: {[t.name for t in tasks]}"
      )

      if not tasks:
        logging.warning(
            "⚠️ No tasks defined in config.json! Please check the file content"
            " and path."
        )
        return

      existing_containers = self.client.containers.list(
          all=True, filters={"label": "managed_by=script_runner"}
      )

      running_task_names = {
          c.labels.get("task_name")
          for c in existing_containers
          if c.status == "running"
      }

      for task in tasks:
        if (
            task.name not in running_task_names
            and task.name not in self.permanently_stopped_tasks
        ):
          logging.info(
              f"✨ New or missing task detected: '{task.name}'. Launching..."
          )
          self.launch_task(task)


  def log_crash(self, report: CrashReport):
    """Save structured crash report into crash_reports.json."""
    reports = []
    if os.path.exists(self.crash_log_file):
      try:
        with open(self.crash_log_file, "r", encoding="utf-8") as f:
          reports = json.load(f)
      except json.JSONDecodeError:
        reports = []

    reports.append(asdict(report))
    with open(self.crash_log_file, "w", encoding="utf-8") as f:
      json.dump(reports, f, ensure_ascii=False, indent=2)

    logging.error(
        f"🚨 Crash recorded for Task '{report.task_name}'. "
        f"Exit Code: {report.exit_code} | OOM: {report.oom_killed}"
    )

  def inspect_and_recover(self):
    """Inspect stopped containers and automatically restart crashed tasks."""
    containers = self.client.containers.list(
        all=True, filters={"label": "managed_by=script_runner"}
    )

    for container in containers:
      status = container.status
      labels = container.labels
      task_name = labels.get("task_name", "Unknown")
      script_path = labels.get("script_path", "")

      if status in ["exited", "dead"]:
        state = container.attrs.get("State", {})
        exit_code = state.get("ExitCode", 0)
        oom_killed = state.get("OOMKilled", False)

        if exit_code != 0 or oom_killed:
          stdout = container.logs(stdout=True, stderr=False).decode("utf-8")
          stderr = container.logs(stdout=False, stderr=True).decode("utf-8")

          current_retries = self.retry_counters.get(task_name, 0) + 1
          self.retry_counters[task_name] = current_retries

          report = CrashReport(
              timestamp=datetime.datetime.utcnow().isoformat() + "Z",
              task_name=task_name,
              script_path=script_path,
              container_id=container.short_id,
              exit_code=exit_code,
              oom_killed=oom_killed,
              stdout=stdout,
              stderr=stderr,
              restart_count=current_retries,
          )
          self.log_crash(report)

          try:
            container.remove(force=True)
          except Exception as e:
            logging.warning(f"Failed to remove failed container: {e}")

          # Anti-flapping retry logic
          if current_retries <= self.max_retries:
            logging.info(
                f"🔄 Retrying task execution ({current_retries}/{self.max_retries}):"
                f" {task_name}"
            )
            tasks = self.load_configs()
            task_cfg = next((t for t in tasks if t.name == task_name), None)
            if task_cfg:
              self.launch_task(task_cfg)
          else:
            logging.critical(
                f"⛔ Task '{task_name}' reached maximum retry limit"
                f" ({self.max_retries}) and was permanently stopped."
            )
            self.permanently_stopped_tasks.add(task_name)

  def start(self):
    """Main supervisor boot up and continuous check loop."""
    logging.info("🚀 Sandbox Supervisor booting up...")

    # Initial boot task sync
    self.sync_tasks()

    # Continuous health check & auto-sync loop
    while True:
      time.sleep(self.check_interval_seconds)
      logging.info("🔍 Routine cycle: Checking for new tasks and container health...")

      # 1. Read JSON config and start newly added tasks
      self.sync_tasks()

      # 2. Inspect containers, log crashes, and restart failed tasks
      self.inspect_and_recover()


if __name__ == "__main__":
  # Automatically locate SandBox_Core directory regardless of current working directory
  CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

  config_file_path = os.path.join(CURRENT_DIR, "config.json")
  crash_log_file_path = os.path.join(CURRENT_DIR, "crash_reports.json")

  supervisor = UnifiedSandboxSupervisor(
      config_path=config_file_path,
      crash_log_file=crash_log_file_path,
      check_interval_seconds=300,  # 5 minutes
      max_retries=3,
  )
  supervisor.start()