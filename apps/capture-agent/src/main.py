"""vivoo local agent entrypoint."""

import argparse
import json
import os
import shutil
from pathlib import Path

from config import load_config, write_example
from local.server import serve_local_agent
from runtime.relay import supervise
from runtime.supervisor import MultiCameraSupervisor


def configure_resources(resource_root: Path | None, config: object) -> None:
    """Prefer the binaries and pose model shipped with vivoo."""
    if resource_root is None:
        return
    bin_dir = resource_root / "bin"
    os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"
    bundled_model = resource_root / "models" / "yolo26n-pose.pt"
    if bundled_model.is_file():
        config.pose_model = str(bundled_model)


def run_self_test(resource_root: Path | None) -> int:
    """Validate the dependencies that must exist on a customer computer."""
    from config import AgentConfig

    config = AgentConfig()
    configure_resources(resource_root, config)
    checks = {
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "ffprobe": bool(shutil.which("ffprobe")),
        "pose_model": Path(config.pose_model).is_file(),
        "pose_runtime": False,
    }
    try:
        from ultralytics import YOLO

        YOLO(config.pose_model)
        checks["pose_runtime"] = True
    except Exception as error:  # pragma: no cover - reported by packaged smoke
        checks["error"] = str(error)
    print(json.dumps(checks))
    return 0 if all(checks.get(name) is True for name in ("ffmpeg", "ffprobe", "pose_model", "pose_runtime")) else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="vivoo local camera agent")
    parser.add_argument("--config", type=Path, default=Path.home() / ".courtvision" / "agent.json")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8781)
    parser.add_argument("--init", action="store_true", help="create a protected empty configuration")
    parser.add_argument("--resources", type=Path, help="directory containing bundled binaries and models")
    parser.add_argument("--cloud-api-url")
    parser.add_argument("--storage-dir")
    parser.add_argument("--relay-rtsp-url")
    parser.add_argument("--relay-supervisor", action="store_true")
    parser.add_argument("--relay-binary", type=Path)
    parser.add_argument("--relay-config", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        raise SystemExit(run_self_test(args.resources))
    if args.init:
        write_example(
            args.config,
            cloud_api_url=args.cloud_api_url,
            storage_dir=args.storage_dir,
            relay_rtsp_url=args.relay_rtsp_url,
        )
        print(f"Configuración creada en {args.config}")
        return
    if not args.config.exists():
        parser.error(f"No existe {args.config}. Ejecutá con --init para crearla.")
    if args.relay_supervisor:
        if not args.relay_binary or not args.relay_config:
            parser.error("--relay-supervisor requiere --relay-binary y --relay-config")
        raise SystemExit(supervise(args.config, args.relay_binary, args.relay_config))
    config = load_config(args.config)
    configure_resources(args.resources, config)
    runtime = MultiCameraSupervisor(args.config, config)
    server = serve_local_agent(runtime, args.host, args.port)
    print(f"Agente local vivoo activo en http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        runtime.stop()
        server.server_close()


if __name__ == "__main__":
    main()
