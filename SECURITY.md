# Security cleanup required during migration

The review of the existing Indigo gate automation found DoorBird credentials
embedded directly in both an enabled trigger script and a local helper shell
script. The request used unencrypted HTTP Basic authentication, and the files
and Indigo database were readable more broadly than credential-bearing assets
should be.

No credentials are copied into this repository, and the alpha plugin does not
perform camera authentication or network requests.

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
5. Search commit history and release artifacts before ever making this
   repository public.

Do not put passwords, tokens, Indigo database files, exported trigger scripts,
or local camera URLs containing credentials in bug reports.
