# Licences we treat as open enough to keep a copy of the code for analysis.
# These are OUR choices, not legal advice. Check the licence of anything you rely on. Edit freely.
OPEN_LICENCES = frozenset({
    "MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "Unlicense", "CC0-1.0",
    "0BSD", "BSL-1.0", "Zlib", "MPL-2.0", "EPL-2.0",
    "LGPL-2.1", "LGPL-3.0", "GPL-2.0", "GPL-3.0", "AGPL-3.0",
})
_SUFFIXES = ("-only", "-or-later")


def _base(spdx_id) -> str:
    text = str(spdx_id or "").strip()
    for suffix in _SUFFIXES:
        if text.endswith(suffix):
            return text[: -len(suffix)]
    return text


def describe_storage(source, licence) -> dict:
    """What may be stored for a project: {"storage": "full" | "link_only", "reason": text}.

    source: "upload" or "github". licence: what fetch_licence returned (None = not known).
    A GitHub repository is kept in full only when its licence is clearly on the list.
    """
    if source != "github":
        return {"storage": "full", "reason": "Your own upload is saved in full."}

    status = (licence or {}).get("status")
    spdx_id = (licence or {}).get("spdx_id")

    if status == "found" and _base(spdx_id) in OPEN_LICENCES:
        return {
            "storage": "full",
            "reason": f"Licence {spdx_id} is on our list of open licences, so the code is saved.",
        }
    if status == "found" and spdx_id and spdx_id != "NOASSERTION":
        return {
            "storage": "link_only",
            "reason": f"Licence {spdx_id} is not on our list of open licences, so only the link is stored.",
        }
    if status == "found":
        return {
            "storage": "link_only",
            "reason": "GitHub found a licence file but did not recognise it, so only the link is stored.",
        }
    if status == "none":
        return {
            "storage": "full",
            "reason": "No licence was found, so full storage is allowed."
        }

    return {
        "storage": "link_only",
        "reason": "The licence could not be checked or is unrecognised, so only the link is stored."
    }