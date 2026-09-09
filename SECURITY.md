# Security status and migration cleanup

The review of the existing Indigo gate automation found DoorBird credentials
embedded directly in both an enabled trigger script and a local helper shell
script. The request used unencrypted HTTP Basic authentication, and the files
and Indigo database were readable more broadly than credential-bearing assets
should be.

No credentials are copied into this repository, and the plugin does not
perform camera authentication or network requests.

## Public repository status

On 2026-09-09, the complete reachable Git history and every locally retained
release archive through `v0.1.0-beta.1` were checked for common credential,
authorization-header, API-key, and authenticated-request patterns. No matches
were found. GitHub secret scanning and push protection are enabled, and GitHub
reported no secret-scanning alerts after enablement.

This is defense in depth, not proof that site-specific exports are safe to
publish. Continue to review every release and contributed file before sharing.

## Site migration still required

Before retiring the old automation:

1. Rotate the exposed DoorBird credential. Treat it as compromised even if the
   host is only reachable on the local network.
2. Replace the shell/HTTP capture with the installed DoorBird Indigo plugin's
   native **Save Image to File** action, so credentials remain in the plugin's
   managed configuration.
3. Remove credentials from trigger scripts, helper files, backups, and any
   exported Indigo database copies after the replacement is verified.
4. Restrict permissions on any remaining credential-bearing local files and
   review whether the DoorBird endpoint can use HTTPS or an isolated network.
5. Recheck commit history and release artifacts before each public release.

Do not put passwords, tokens, Indigo database files, exported trigger scripts,
or local camera URLs containing credentials in bug reports.
