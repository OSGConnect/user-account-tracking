#!/usr/bin/env python3
import json
import logging
import sys
import smtplib

from collections import defaultdict
from datetime import datetime
from datetime import timezone
from email.mime.text import MIMEText
from enum import Enum
from pathlib import Path
from typing import List, Set, Union

from client import UserApiClient

from tqdm import tqdm

DATE_FMT = "%Y-%b-%d %H:%M:%S.%f %Z"

log = logging.getLogger("reporter")

logging.basicConfig(level=logging.DEBUG)

class GroupMemberState(Enum):
    """Possible group membership states"""
    NONMEMBER = "nonmember"
    PENDING = "pending"
    ACTIVE = "active"
    ADMIN = "admin"
    DISABLED = "disabled"

def get_snapshot(save=True) -> dict:
    """
    Dump a snapshot of the data base into ./snapshots/YYYYMMDD_snapshot.json

    The snapshot contains only information needed to the following for a given
    time period:
    - new account requests
    - new account requests that have already been added to a training project
    - new account requests that have already been added to a non-training project
    - new accounts accepted
    - new accounts accepted and have been added to a training project
    - new accounts accepted and have been added to a non-training project

    The snapshot is formatted as follows:
    {
        "date": "YYYY-Mon-DD HH:MM:SS.MS UTC",
        "users": {
            "<user_name>": {
                "osg_state": "<active | pending | ...>",
                "joing_date": "YYYY-Mon-DD HH:MM:SS.MS UTC",
                "groups": {
                    "<group_name>": "<active | pending | ...>",
                    ...
                } 
            }, ...
        }
    }

    :param save: whether or not to save snapshot to disk, defaults to True
    :type save: bool
    :return: snapshot just written
    :rtype: dict
    """
    TOP_DIR = Path(__file__).parent.resolve()
    client = UserApiClient(TOP_DIR / "token_DO_NOT_VERSION")
    
    snapshot = defaultdict(dict)

    # get the state of all users in the root.osg group
    osg_states = client.get_group_members("root.osg")
    for s in osg_states:
        snapshot[s["user_name"]]["osg_state"] = s["state"]

    # get the join date of all users (it is expected that all users belong to root.osg)
    users = client.get_users()
    for u in users:
        if u["kind"].lower() == "user" and u["metadata"]["unix_name"] in snapshot:
            u = u["metadata"]
            snapshot[u["unix_name"]]["join_date"] = u["join_date"]

    # get the membership information from each group (len(groups) number of api requests...)
    groups = client.get_group_list()
    for group_name in tqdm(groups):
        memberships = client.get_group_members(group_name)
        for m in memberships:
            if "groups" not in snapshot[m["user_name"]]:
                snapshot[m["user_name"]]["groups"] = dict()

            snapshot[m["user_name"]]["groups"][group_name] = m["state"]

    log.info("collected {num} users in the root.osg group".format(num=len(snapshot)))

    # add date snapshot was recorded 
    snapshot = {
        "date": datetime.now(timezone.utc).strftime(DATE_FMT),
        "users": snapshot
    }

    # setup directory for snapshot files
    snapshot_dir = TOP_DIR / "snapshots"
    snapshot_dir.mkdir(exist_ok=True)

    snapshot_file = "{date}_snapshot.json".format(date=datetime.now().strftime("%Y%m%d"))
    snapshot_file = snapshot_dir / snapshot_file

    with snapshot_file.open("w") as f:
        json.dump(snapshot, f, indent=1)

    log.info("snapshot written to {file}".format(file=snapshot_file))

    return snapshot

def get_latest_snapshot_on_disk() -> Union[Path, None]:
    """
    Returns the a path object to the latest snapshot file in ./snapshots.

    :return: path to the latest snapshot file or None if none is found
    :rtype: Union[Path, None]
    """
    SNAPSHOT_DIR = Path(__file__).parent.resolve() / "snapshots"

    latest_snapshot_file = None
    latest_snapshot_date = datetime.min

    if SNAPSHOT_DIR.is_dir():
        for f in SNAPSHOT_DIR.iterdir():
            if f.name.endswith("_snapshot.json"):
                with f.open("r") as curr_snapshot_file:
                    curr_snapshot_date = json.load(curr_snapshot_file)["date"]
                    curr_snapshot_date = datetime.strptime(curr_snapshot_date, DATE_FMT)

                    if curr_snapshot_date > latest_snapshot_date:
                        latest_snapshot_date = curr_snapshot_date
                        latest_snapshot_file = f

    return latest_snapshot_file

def send_report(recipients: List[str], msg_content: str) -> None:

    # TODO: parametrize email recipients.. (or load from file to keep from versioning)
    # TODO: needs exception/error handling

    # get email credentials
    EMAIL_CREDENTIALS = Path(__file__).parent.resolve() / "email_credentials_DO_NOT_VERSION"
    with EMAIL_CREDENTIALS.open("r") as f:
        pw = f.read().strip()
    
    title = 'My title'
    message = MIMEText(msg_content, 'html')

    message['From'] = 'OSG <osg.user.reporting@gmail.com>'
    message['To'] = 'Ryan <serve@server.com>'
    #message['Cc'] = 'someone <server@server.com>'
    message['Subject'] = 'Any subject'

    msg_full = message.as_string()

    server = smtplib.SMTP('smtp.gmail.com:587')
    server.starttls()
    server.login('osg.user.reporting@gmail.com', pw)
    server.sendmail('osg.user.reporting@gmail.com', recipients, msg_full)
    server.quit()

def get_training_groups() -> Set[str]:
    """
    Returns the list of training groups in ./training_groups.json as a set.

    :return: training groups
    :rtype: Set[str]
    """
    try:
        training_groups_file = Path(__file__).parent.resolve() / "training_groups.json"
        with training_groups_file.open("r") as f:
            training_groups = set(json.load(f))

        log.info("found training groups: {tg} in {p}".format(
            tg=training_groups,
            p=training_groups_file
        ))

        return training_groups

    except FileNotFoundError:
        log.error("Unable to find {p}, no training groups set".format(
            p=training_groups_file
        ))
        raise
    except json.JSONDecodeError:
        log.error("Unable to decode {p}, possible formatting error".format(p=training_groups_file))
        raise
    


### New Account Request Reporting ##############################################
def get_new_account_requests(prev_snapshot: dict, curr_snapshot: dict) -> List[str]:
    """
    Gets all new accounts requests that came in during
    prev_snapshot["date"] < user_join_date <= curr_snapshot["date"]. 

    :param prev_snapshot: snapshot previously recorded
    :type prev_snapshot: dict
    :param curr_snapshot: snapshot just recorded
    :type curr_snapshot: dict
    :return: list of users who had requested accounts since the last snapshot was taken
    :rtype: list
    """
    start_date = datetime.strptime(prev_snapshot["date"], DATE_FMT)
    end_date = datetime.strptime(curr_snapshot["date"], DATE_FMT)

    accounts = list()
    for u_name, u_info in curr_snapshot["users"].items():
        # join_date is not present for some users (for example onces that are
        # part of groups other than root.osg)
        if "join_date" in u_info:
            join_date = datetime.strptime(u_info["join_date"], DATE_FMT)

            if start_date < join_date and join_date <= end_date:
                accounts.append(u_name)
    
    log.info("found {n} new account requests from {start} to {end}".format(
        n=len(accounts),
        start=start_date,
        end=end_date
    ))

    return accounts

def get_new_account_requests_in_training_group(
            new_act_reqs: List[str], 
            curr_snapshot: dict, 
            training_projects: Set[str]
        ) -> List[str]:
    """
    Gets all new account requests that have already been added to a training
    group. "Added to a training group" is defined as showing up as a member in
    a training group with state=<active | pending>.

    :param new_act_reqs: new accounts requested since the last snapshot was taken
    :type new_act_reqs: List[str]
    :param curr_snapshot: snapshot just recorded
    :type curr_snapshot: dict
    :param training_projects: predefined set of training projects to search for
    :type training_projects: Set[str]
    :return: list of users who have requested accounts since the last snapshot was taken and have also been added to a training project
    :rtype: List[str]
    """
    accounts = list()

    for user in new_act_reqs:
        user_groups = curr_snapshot["users"][user]["groups"]

        for group_name, state in user_groups.items():
            if group_name in training_projects and\
                state in {GroupMemberState.ACTIVE.value, GroupMemberState.PENDING.value}:

                accounts.append(user)
                break
    
    log.info(
        "found {n} new account requests that have already been added to a training project".format(
            n=len(accounts)
        )
    )

    return accounts


def get_new_account_requests_in_non_training_group(
        new_act_reqs: List[str], 
        curr_snapshot: dict, 
        training_projects: Set[str], 
        exclude={"root", "root.osg"}
    ) -> List[str]:
    """
    Gets all new account requests that have already been added to a non training
    group. "Added to a non training group" is defined as showing up as a member in
    a group that is neither of any of the groups in "exclude" and "training_projects"
    and having a group state=<active | pending>. 

    :param new_act_reqs: new accounts requested since the last snapshot was taken
    :type new_act_reqs: List[str]
    :param curr_snapshot: snapshot just recorded
    :type curr_snapshot: dict
    :param training_projects: set of training projects to exclude
    :type training_projects: Set[str]
    :param exclude: non-training projects to exclude, defaults to {"root", "root.osg"}
    :type exclude: dict, optional
    :return: list of users who have requested accounts since the last snapshot was taken and have also been added to a non training project
    :rtype: List[str]
    """
    exclude.update(training_projects)
    accounts = list()

    for user in new_act_reqs:
        user_groups = curr_snapshot["users"][user]["groups"]

        for group_name, state in user_groups.items():
            if group_name not in exclude and\
                state in {GroupMemberState.ACTIVE.value, GroupMemberState.PENDING.value}:
            
                accounts.append(user)
                break
    
    log.info(
        "found {n} new account requests that have already been added to a non training project (excluding {excluded})".format(
            n=len(accounts),
            excluded=exclude
        )
    )

    return accounts


### New Accounts Accepted Reporting ############################################
def get_new_accounts_accepted(prev_snapshot: dict, curr_snapshot: dict) -> List[str]:
    """
    Gets all accounts that have been accepted since the last snapshot.  An "accepted
    account" is defined as having its state moved from "pending" to "active".

    :param prev_snapshot: snapshot previously recorded
    :type prev_snapshot: dict
    :param curr_snapshot: snapshot just recorded
    :type curr_snapshot: dict
    :return: list of users whos accounts have been accepted since the last snapshot was taken
    :rtype: List[str]
    """
    start_date = datetime.strptime(prev_snapshot["date"], DATE_FMT)
    end_date = datetime.strptime(curr_snapshot["date"], DATE_FMT)

    accounts = list()

    for u_name, u_info in prev_snapshot["users"].items():

        # not all memebers are part of "root.osg", skip those that are not 
        if "root.osg" in u_info["groups"]:
            if u_info["groups"]["root.osg"] == GroupMemberState.PENDING.value \
                and curr_snapshot["users"][u_name]["groups"]["root.osg"] == GroupMemberState.ACTIVE.value:

                accounts.append(u_name)
        else:
            log.warning("user: {u} does not have group root.osg".format(u=u_name))
    
    log.info(
        "found {n} new accounts that have been accepted from {start} to {end}".format(
            n=len(accounts),
            start=start_date,
            end=end_date
        )
    )

    return accounts

def get_new_accounts_accepted_in_training_group(
        new_acts_accepted: List[str], 
        curr_snapshot: dict, 
        training_projects: Set[str]
    ) -> List[str]:
    """
    Gets all accounts that have been accepted and added to a training project.
    "Added to a training group" is defined as showing up as a member in a training
    group with state=<active | pending>.

    :param new_acts_accepted: new accounts accepted since the last snapshot was taken
    :type new_acts_accepted: List[str]
    :param curr_snapshot: snapshot just recorded
    :type curr_snapshot: dict
    :param training_projects: predefined set of training projects to search for
    :type training_projects: Set[str]
    :return: list of users whos accounts have been accepted and added to a training project
    :rtype: List[str]
    """

    accounts = list()

    for user in new_acts_accepted:
        user_groups = curr_snapshot["users"][user]["groups"]

        for group_name, state in user_groups.items():
            if group_name in training_projects and\
                state in {GroupMemberState.ACTIVE.value, GroupMemberState.PENDING.value}:

                accounts.append(user)
                break

    log.info(
        "found {n} accounts that have been accepted and added to a training project".format(
            n=len(accounts)
        )
    )

    return accounts

def get_new_accounts_accepted_in_non_training_group(
        new_acts_accepted: List[str],
        curr_snapshot: dict, 
        training_projects: Set[str], 
        exclude: Set[str] = {"root", "root.osg"}
    ) -> List[str]:
    """
    Gets all accounts that have been accepted since the last snapshot and have
    been already added to a non training group. "Added to a non training group" is
    defined as showing up as a member in a group that is neither in any of the 
    groups in "exclude" and "training_projects" and having a group state=<active | pending>.

    :param new_acts_accepted: new accounts accepted since the last snapshot was taken
    :type new_acts_accepted: List[str]
    :param curr_snapshot: snapshot just recorded
    :type curr_snapshot: dict
    :param training_projects: predefiend set of training projects to exclude
    :type training_projects: Set[str]
    :param exclude: non-training projects to exclude, defaults to {"root", "root.osg"}
    :type exclude: Set[str], optional
    :return: list of users whos accounts have been accepted and added to a non training project
    :rtype: List[str]
    """
    exclude.update(training_projects)
    accounts = list()

    for user in new_acts_accepted:
        user_groups = curr_snapshot["users"][user]["groups"]

        for group_name, state in user_groups.items():
            if group_name not in exclude and\
                state in {GroupMemberState.ACTIVE.value, GroupMemberState.PENDING.value}:

                accounts.append(user)
                break
    
    log.info(
        "found {n} new accounts accepted that have already been added to a non training project (excluding {excluded})".format(
            n=len(accounts),
            excluded=exclude
        )
    )

    return accounts


if __name__=="__main__":
    # TODO: account for users that were deleted since the previous snapshot
    # was taken (we will get a keyerror in that case)
    # TODO: implement snapshot cleaner (limit 2 last 2 snapshots)

    # TODO: cleanup smtp code; add error checking; logging

    previous_snapshot_file = get_latest_snapshot_on_disk()

    if not previous_snapshot_file:
        log.info("No previous snapshot found, exiting")
        sys.exit(1)

    with previous_snapshot_file.open("r") as f:
        previous_snapshot = json.load(f)
    
    current_snapshot = get_snapshot(save=True)

    previous_snapshot_date = datetime.strptime(previous_snapshot["date"], DATE_FMT)
    current_snapshot_date = datetime.strptime(current_snapshot["date"], DATE_FMT)
    report_duration_in_days = (current_snapshot_date - previous_snapshot_date).days
    
    training_groups = get_training_groups()

    # new account requests
    new_account_requests = get_new_account_requests(
            prev_snapshot=previous_snapshot,
            curr_snapshot=current_snapshot
        )

    new_account_requests_in_training_group = get_new_account_requests_in_training_group(
        new_act_reqs=new_account_requests,
        curr_snapshot=current_snapshot,
        training_projects=training_groups
    )

    new_account_requests_in_non_training_group = get_new_account_requests_in_non_training_group(
        new_act_reqs=new_account_requests,
        curr_snapshot=current_snapshot,
        training_projects=training_groups
    )

    # accounts accepted
    new_accounts_accepted = get_new_accounts_accepted(
        prev_snapshot=previous_snapshot,
        curr_snapshot=current_snapshot
    )

    new_accounts_accepted_in_training_group = get_new_accounts_accepted_in_training_group(
        new_acts_accepted=new_accounts_accepted,
        curr_snapshot=current_snapshot,
        training_projects=training_groups
    )

    new_accounts_accepted_in_non_training_group = get_new_accounts_accepted_in_non_training_group(
        new_acts_accepted=new_accounts_accepted,
        curr_snapshot=current_snapshot,
        training_projects=training_groups
    )

    report = """
    <p>Account Reporting: {start} to {end} ({dur} days)</p>
    <ul>
        <li>New Accounts Requested: {nar}</li>
            <ul>
                <li>AND in Training Group: {nar_tr}</li>
                <li>AND in Non Training Group: {nar_ntr}</li>
            </ul>
        <li>New Accounts Accepted: {naa}</li>
            <ul>
                <li>AND in Training Group: {naa_tr}</li>
                <li>AND in Non Training Group: {naa_ntr}</li>
            </ul>
    </ul>
    """.format(
        start=previous_snapshot["date"],
        end=current_snapshot["date"],
        dur=report_duration_in_days,
        nar=len(new_account_requests),
        nar_tr=len(new_account_requests_in_training_group),
        nar_ntr=len(new_account_requests_in_non_training_group),
        naa=len(new_accounts_accepted),
        naa_tr=len(new_accounts_accepted_in_training_group),
        naa_ntr=len(new_accounts_accepted_in_non_training_group)
    )

    send_report(recipients=["server@server.com"], msg_content=report)
