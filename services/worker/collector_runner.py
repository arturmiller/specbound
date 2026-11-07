"""Execute a specifically approved collector using an isolated Docker container."""

import json
import re
from dataclasses import dataclass

from app.collector_contracts import (
    CollectorContractError,
    validate_request,
    validate_response,
)
from docker.errors import DockerException, NotFound
from docker.types import LogConfig
from requests.exceptions import ConnectionError, ReadTimeout
from urllib3.exceptions import ReadTimeoutError

MAX_REQUEST = 64 * 1024
MAX_OUTPUT = 1024 * 1024
IMAGE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9./:_-]*@sha256:[0-9a-f]{64}$")


@dataclass(frozen=True)
class ApprovedCollector:
    """An explicit operator-controlled image and command, never pack approval."""

    image: str
    command: tuple[str, ...]

    def __post_init__(self):
        if (
            not IMAGE.fullmatch(self.image)
            or len(self.command) < 2
            or not all(isinstance(value, str) and value for value in self.command)
        ):
            raise ValueError("Approval requires a digest and an explicit command with arguments")


@dataclass(frozen=True)
class CollectorResult:
    status: str
    reason: str
    observations: tuple = ()


class RunnerCleanupError(RuntimeError):
    """The runner cannot establish that its container has been removed."""


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _read_timed_out(error):
    """Requests may wrap urllib3's read timeout in a ConnectionError."""
    pending = [error]
    seen = set()
    while pending:
        item = pending.pop()
        if id(item) in seen:
            continue
        seen.add(id(item))
        if isinstance(item, (ReadTimeout, ReadTimeoutError)):
            return True
        if isinstance(item, BaseException):
            pending.extend(item.args)
            pending.extend((item.__cause__, item.__context__))
    return False


def run_collector(client, provider, request, approved, *, timeout_seconds=10):
    """Run once. No pull, network, credentials, mounts, or implicit approvals."""
    if not 0 < timeout_seconds <= 60:
        raise ValueError("timeout must be between zero and 60 seconds")
    try:
        validate_request(provider, request)
        runtime = provider["manifest"]["runtime"]
        if (
            not isinstance(approved, ApprovedCollector)
            or runtime["image"] != approved.image
            or tuple(runtime.get("entrypoint", ())) != approved.command
            or request["credentialsRef"] is not None
        ):
            return CollectorResult("UNKNOWN", "collector-not-approved")
        payload = json.dumps(request, ensure_ascii=True, separators=(",", ":"))
        if len(payload.encode("utf-8")) > MAX_REQUEST:
            return CollectorResult("UNKNOWN", "request-too-large")
    except (CollectorContractError, KeyError, TypeError, ValueError):
        return CollectorResult("UNKNOWN", "invalid-request")

    container = None
    try:
        image = client.images.get(approved.image)  # Never pull an image implicitly.
        if image.attrs.get("Config", {}).get("Volumes"):
            return CollectorResult("UNKNOWN", "image-declares-volumes")
        container = client.containers.create(
            approved.image,
            entrypoint=[approved.command[0]],
            command=list(approved.command[1:]),
            environment={"SPECBOUND_REQUEST": payload},
            use_config_proxy=False,
            network_mode="none",
            read_only=True,
            user="65534:65534",
            cap_drop=["ALL"],
            security_opt=["no-new-privileges"],
            pids_limit=64,
            mem_limit="128m",
            memswap_limit="128m",
            nano_cpus=500_000_000,
            healthcheck={"Test": ["NONE"]},
            log_config=LogConfig(type="json-file", config={"max-size": "1m", "max-file": "1"}),
            labels={"org.specbound.collector": "true"},
        )
        container.start()
        try:
            result = container.wait(timeout=timeout_seconds)
        except (ReadTimeout, ConnectionError) as exc:
            reason = "timeout" if _read_timed_out(exc) else "runtime-unavailable"
            return CollectorResult("UNKNOWN", reason)
        if result.get("StatusCode") != 0:
            return CollectorResult("UNKNOWN", "collector-failed")
        output = container.logs(stdout=True, stderr=False)
        if len(output) > MAX_OUTPUT:
            return CollectorResult("UNKNOWN", "output-too-large")
        response = json.loads(output, object_pairs_hook=_unique_pairs)
        validate_response(provider, request, response)
        return CollectorResult("OBSERVED", "ok", tuple(response["observations"]))
    except (DockerException, OSError):
        return CollectorResult("UNKNOWN", "runtime-unavailable")
    except (CollectorContractError, ValueError, UnicodeError, TypeError):
        return CollectorResult("UNKNOWN", "invalid-response")
    finally:
        if container is not None:
            try:
                # Docker's forced removal kills a still-running collector first.
                container.remove(force=True)
            except NotFound:
                pass
            except DockerException as exc:
                raise RunnerCleanupError("Collector container could not be removed") from exc
