from enum import auto, Flag

class Capabilities(Flag):
    FILE_EXECUTE = auto()
    CODE_EXECUTE = auto()
    GIT_EXECUTE = auto()
    WEB_EXECUTE = auto()

AGENT_CAPABILITIES: dict[str, Capabilities] = {
    "File_Agent": Capabilities.FILE_EXECUTE,
    "Code_Agent": Capabilities.CODE_EXECUTE,
    "Git_Agent": Capabilities.GIT_EXECUTE,
    "Web_Agent": Capabilities.WEB_EXECUTE,
}