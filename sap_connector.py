# ======================================================================
#  File......: sap_connector.py
#  Purpose...: Arthrex SAP SSO connector for PyRFC (SMD / SMP aware)
#  Version...: 1.2.0
#  Date......: 2026-01-05
#  Author....: Edwin Rodriguez (Arthrex IT SAP COE)
#
#  Goals:
#    - No reliance on user env vars (SNC_LIB not required)
#    - Auto-detect sapcrypto.dll from common Secure Login Client installs
#    - Support system switch (SMD/SMP) and keep ini SNC partner synced
#    - Do NOT fail fast: if SNC init fails for one DLL path, try next
# ======================================================================

from __future__ import annotations

import os
import getpass
import configparser
from typing import Tuple, List, Optional

from pyrfc import Connection, CommunicationError, LogonError


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

HERE = os.path.abspath(os.path.dirname(__file__))
CONFIG_PATH = os.path.join(HERE, "sap_sso_config.ini")


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _detect_user_snc() -> Tuple[str, str]:
    """
    Determine SNC myname for the current user.

    Keep this aligned with your SLC/SNC setup. If your environment
    requires a fully-qualified SNC subject, update this format.
    """
    user = getpass.getuser()
    user_id = user
    snc_myname = f"p:CN={user}"
    return snc_myname, user_id


def _candidate_crypto_libs() -> List[str]:
    """
    Return a prioritized list of candidate sapcrypto.dll paths.
    We prefer 64-bit Program Files first, then fall back.
    """
    candidates = [
        # 64-bit (preferred)
        r"C:\Program Files\SAP\FrontEnd\SecureLogin\lib\sapcrypto.dll",
        r"C:\Program Files\SAP\FrontEnd\SecureLoginClient\lib\sapcrypto.dll",
        r"C:\Program Files\SAP\FrontEnd\SecureLoginClient\lib\sapcrypto.dll",
        r"C:\Program Files\SAP\FrontEnd\SecureLogin\lib\sapcrypto.dll",

        # Sometimes installed under SAP GUI/NW RFC SDK locations (varies)
        r"C:\Program Files\SAP\NW RFC SDK\lib\sapcrypto.dll",
        r"C:\Program Files\SAP\NW RFC SDK\lib\sapcrypto.dll",

        # 32-bit (last resort; only works if you are truly running 32-bit Python/PyRFC)
        r"C:\Program Files (x86)\SAP\FrontEnd\SecureLogin\lib\sapcrypto.dll",
        r"C:\Program Files (x86)\SAP\FrontEnd\SecureLoginClient\lib\sapcrypto.dll",
    ]

    # De-dupe while keeping order
    seen = set()
    out = []
    for p in candidates:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _find_crypto_libs_existing() -> List[str]:
    """
    Filter candidates to only those that exist on disk.
    """
    libs = [p for p in _candidate_crypto_libs() if os.path.exists(p)]
    return libs


def _ensure_config(default_partner: str) -> str:
    """
    Ensure sap_sso_config.ini exists and contains the desired SNC partnername.
    Returns the configured partnername.
    """
    cfg = configparser.ConfigParser()
    if os.path.exists(CONFIG_PATH):
        cfg.read(CONFIG_PATH)

    if "SAP" not in cfg:
        cfg["SAP"] = {}

    current = (cfg["SAP"].get("snc_partnername") or "").strip()
    if current != default_partner:
        cfg["SAP"]["snc_partnername"] = default_partner
        with open(CONFIG_PATH, "w") as f:
            cfg.write(f)
        print(f"✅ Set SNC partner in {CONFIG_PATH} to '{default_partner}'")

    return cfg["SAP"]["snc_partnername"].strip()


def _system_to_host_partner(system: Optional[str], host: str) -> Tuple[str, str, str]:
    """
    Decide host + SNC partner based on system selection.
    Returns (system, host, partner).
    """
    if system is None:
        # Infer from host
        system = "SMP" if "smp" in (host or "").lower() else "SMD"
    system = system.upper()

    if system == "SMP":
        host = "vartsmpapp1"
        partner = "p/sapsso:CN=SMP"
    else:
        system = "SMD"
        host = "vartsmdpas"
        partner = "p/sapsso:CN=SMD"

    return system, host, partner


# ---------------------------------------------------------------------
# Public connector
# ---------------------------------------------------------------------

def connect_sso(
    host: str = "vartsmdpas",
    sysnr: str = "00",
    client: str = "100",
    system: Optional[str] = None,
):
    """
    Establish an SSO connection to SAP via Secure Login Client.

    Key behavior:
      - No env var required: auto-detect sapcrypto.dll from common locations
      - System-aware:
          SMD -> vartsmdpas + p/sapsso:CN=SMD
          SMP -> vartsmpapp1 + p/sapsso:CN=SMP
      - Non-fatal first failure:
          If one sapcrypto.dll fails to initialize (SNCERR_INIT), try the next.

    Returns:
      pyrfc.Connection
    """
    system, host, partner_default = _system_to_host_partner(system, host)

    # Keep ini aligned to selected system partner
    snc_partner = _ensure_config(partner_default)

    snc_myname, user_id = _detect_user_snc()

    # Find crypto libs on disk
    crypto_libs = _find_crypto_libs_existing()
    if not crypto_libs:
        raise RuntimeError(
            "No sapcrypto.dll found in common Secure Login Client locations.\n"
            "Install SAP Secure Login Client (64-bit preferred) or ensure sapcrypto.dll is present."
        )

    last_error = None

    # Try each crypto lib until one works
    for snc_lib in crypto_libs:
        params = dict(
            ashost=host,
            sysnr=sysnr,
            client=client,
            lang="EN",
            snc_mode="1",
            snc_qop="9",
            snc_lib=snc_lib,
            snc_partnername=snc_partner,
            snc_myname=snc_myname,
        )

        print(f"Connecting to SAP ({host}, system={system}) as {user_id} via SSO ...")
        print(f"   Trying SNC library: {snc_lib}")

        try:
            conn = Connection(**params)
            print("SAP SSO connection established.")
            return conn

        except CommunicationError as e:
            last_error = e
            msg = str(e)

            if "SNCERR_INIT" in msg or "SncPDLInit" in msg:
                print("⚠️ SNC init failed for this sapcrypto.dll; trying next candidate...")
                continue

            if "Actual server name differs" in msg or "SncPEstablishContext" in msg:
                print("⚠️ SNC handshake warning; trying next candidate...")
                continue

            print("⚠️ RFC CommunicationError; trying next candidate...")
            continue

        except LogonError as e:
            last_error = e
            print("⚠️ SAP LogonError; trying next candidate...")
            continue

        except Exception as e:
            last_error = e
            print("⚠️ Unexpected error; trying next candidate...")
            continue

    raise RuntimeError(
        "Unable to establish SAP SSO connection after trying all detected sapcrypto.dll candidates.\n"
        f"Last error: {last_error}"
    ) from last_error
