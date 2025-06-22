# Important
This has not been validate for production readiness.

# About
This is a repository that contains the code for an execution engine inspired by the [ctfd-fileupload](https://github.com/ghidragolf/ctfd-fileupload)
plugin, it uses uses two services one that accepts requests pushes them to a Rabbitmq queue and one 
that consumes these messages and interacts with the [Piston](https://github.com/engineer-man/piston) 
execution engine to execute the code.

# Usage
## How does the submission work
Requests are submitted to the `/submit` endpoint following the format:
```json
{
    "code": "print('hello')",
    "language": "python",
    "settings": "fB...",
}
```
The settings are encrypted using the `./utils/settings/settings.py` script after changing the `settings` 
dictionary values.
## Usage: Challenge maker perspective
1. Use the `./utils/settings/settings.py` to encrypt the settings to use for your challenge.
2. Update the `SETTINGS` variable in the `./utils/submit/submit.py` with the output of the settings script 
3. Add the `submit.py` to the list of files to be given to the participants.

