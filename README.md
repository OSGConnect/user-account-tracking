# User Account Reporting Tool

This user account reporting tool has been developed to automate the process of
reporting the number of weekly new account requests and new accounts accepted
through OSG Connect. 

To accomplish this, the script `generate_user_report.py` pulls user information
from the OSG Connect User Database, saves a snapshot of the database (only 
information needed to generate the report is saved), and compares it to a 
previously saved snapshot in order to count the metrics previously mentioned.

`generate_user_report.py` will send an HTML email report to the given recipients
upon completion. 

## Prerequisites

1. a file in the current working directory called `email_credentials_DO_NOT_VERSION`
    with the password to the email account used to send the email report
2. a file in the current working directory called `token_DO_NOT_VERSION` with a 
    token that has access to use the OSG User Account Database REST endpoint
3. the required python3 packages installed (run `pip3 install -r requirements.txt`)

## Usage

```
usage: generate_user_report.py [-h] recipients [recipients ...]

Collects user account metrics, generates an html report, and sends it to the given recipients.

positional arguments:
  recipients  recipients to which the report will be sent

optional arguments:
  -h, --help  show this help message and exit
```

Example: `python3 generate_user_report.py email@domain`

