"""Version-derived release metadata shared by packaging and verification."""
import re

from validation import require


def channel(version):
    number = r"(?:0|[1-9][0-9]*)"
    match = re.fullmatch(rf"{number}\.{number}\.{number}(?:-(alpha|beta|rc)\.{number})?", version)
    require(match, "Unsupported release version; use stable SemVer or alpha/beta/rc with a numeric suffix")
    return match[1] or "stable"


def portable_guide(template, version):
    stage = channel(version)
    status = ("Stable release for the documented Windows/Linux portable CLI."
              if stage == "stable" else
              f"Experimental {stage} prerelease for the Windows/Linux portable CLI; not a stable release.")
    require(template.count("@RELEASE_STATUS@") == 1, "Portable guide needs one version-derived release status")
    result = template.replace("@VERSION@", version).replace("@RELEASE_STATUS@", status)
    require(not re.search(r"@[A-Z_]+@", result), "Unresolved portable guide placeholder")
    return result
