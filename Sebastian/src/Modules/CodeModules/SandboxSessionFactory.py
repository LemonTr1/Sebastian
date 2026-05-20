from agents.sandbox import Manifest
from agents.sandbox.sandboxes import DockerSandboxClient, DockerSandboxClientOptions
from agents.sandbox.session import SandboxSession
from docker import from_env

class SandboxSessionFactory:
    @staticmethod
    async def get_session(manifest: Manifest)-> SandboxSession:
        client = DockerSandboxClient(from_env())
        return await client.create(manifest=manifest, options=DockerSandboxClientOptions(image="sebastian:local"))