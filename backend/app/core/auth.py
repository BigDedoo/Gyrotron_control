import os
import logging
from ldap3 import Server, Connection, ALL, NTLM

logger = logging.getLogger(__name__)

# Configuration
LDAP_SERVER_HOST = os.getenv("LDAP_SERVER_HOST", "ccsvad05.in2p3.fr")
LDAP_DOMAIN = os.getenv("LDAP_DOMAIN", "grenoble.in2p3.fr")

def authenticate_user(username: str, password: str) -> bool:
    """
    Authenticates a user against the Active Directory server.
    Supports user formats: 'username', 'domain\\username', 'username@domain.com'
    """
    if not username or not password:
        return False
        
    # Standardize the username format for AD binding
    # Best practice for AD is often userPrincipalName (user@domain.com) or Down-Level Logon Name (DOMAIN\user)
    if "\\" in username:
        # Already has domain prefix
        user_dn = username
    elif "@" in username:
        # Already has domain suffix (UPN)
        user_dn = username
    else:
        # Assume default domain
        user_dn = f"{username}@{LDAP_DOMAIN}"

    try:
        # Connect to the server
        # use_ssl=True is recommended for production (port 636), but we mock the port 389 starttls for now or plain text
        # The user provided port 389 so we start with standard TCP
        server = Server(LDAP_SERVER_HOST, port=389, get_info=ALL)
        
        # Attempt to bind with the provided credentials
        # auto_bind=True will perform the Bind operation immediately
        conn = Connection(server, user=user_dn, password=password, auto_bind=True)
        
        # If we reach here, authentication was successful
        conn.unbind()
        return True
    except Exception as e:
        logger.error(f"LDAP Authentication Failed for {user_dn}: {e}")
        return False
