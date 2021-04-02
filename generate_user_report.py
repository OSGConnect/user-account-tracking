#!/usr/bin/env python3
import logging
import sys

from collections import defaultdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Set

from client import UserApiClient

from tqdm import tqdm

DATE_FMT = "%Y-%b-%d %H:%M:%S.%f %Z"

log = logging.getLogger("reporter")

logging.basicConfig(level=logging.INFO)

class GroupMemberState(Enum):
    """Possible group membership states"""
    NONMEMBER = "nonmember"
    PENDING = "pending"
    ACTIVE = "active"
    ADMIN = "admin"
    DISABLED = "disabled"

def dump_snapshot() -> None:
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
        "date": "YYYY-MM-DD HH:MM:SS.MS UTC",
        "users": {
            "<user_name>": {
                "osg_state": "<active | pending | ...>",
                "joing_date": "YYYY-MM-DD HH:MM:SS.MS UTC",
                "groups": {
                    "<group_name>": "<active | pending | ...>",
                    ...
                } 
            }, ...
        }
    }
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
        "date": datetime.now(timezone.utc).strftime("%y-%b-%d %H:%M:%S.%f %Z"),
        "users": snapshot
    }

    # setup directory for snapshot files
    snapshot_dir = TOP_DIR / "snapshots"
    snapshot_dir.mkdir(exist_ok=True)

    snapshot = "{date}_snapshot.json".format(date=datetime.now().strftime("%Y%m%d"))
    snapshot = TOP_DIR / snapshot

    with snapshot.open("w") as f:
        json.dump(snapshot, f, indent=1)

    log.info("snapshot written to {file}".format(file=f_name))

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

    new_act_reqs = list()
    for u_name, u_info in curr_snapshot["users"].items():
        join_date = datetime.strptime(u_info["join_date"], DATE_FMT)

        if start_date < join_date and join_date <= end_date:
            new_act_reqs.append(u_name)
    
    log.info("found {n} new account requests from {start} to {end}".format(
        n=len(new_act_reqs),
        start=start_date,
        end=end_date
    ))

    return new_act_reqs

def get_new_account_requests_in_training_group(
            new_act_reqs: List[str], 
            curr_snapshot: dict, 
            training_projects: Set[str]
        ) -> List[str]:
    """
    Gets all new account requests that have already been added to a training
    group. "Added to a training group" is defined as showing up as a memeber in
    the group with state=<active | pending>.

    :param new_act_reqs: new accounts requested since the last snapshot was taken
    :type new_act_reqs: List[str]
    :param curr_snapshot: snapshot just recorded
    :type curr_snapshot: dict
    :param training_projects: predefined set of training projects to search for
    :type training_projects: Set[str]
    :return: list of users who have requested accounts since the last snapshot was taken and have also been added to a training project
    :rtype: List[str]
    """
    new_act_reqs_in_training_grp = list()

    for user in new_act_reqs:
        user_groups = curr_snapshot["users"][user]["groups"]

        for group_name, state in user_groups.items():
            if group_name in training_projects and\
                state in {GroupMemberState.ACTIVE.value, GroupMemberState.PENDING.value}:

                new_act_reqs_in_training_grp.append(user)
                break
    
    log.info(
        "found {n} new account requests that have already been added to a training project".format(
            n=len(new_act_reqs_in_training_grp)
        )
    )

    return new_act_reqs_in_training_grp


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
    and having a state=<active | pending>. 

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
    new_act_reqs_in_non_training_grp = list()

    for user in new_act_reqs:
        user_groups = curr_snapshot["users"][user]["groups"]

        for group_name, state in user_groups.items():
            if group_name not in exclude and\
                state in {GroupMemberState.ACTIVE.value, GroupMemberState.PENDING.value}:
            
                new_act_reqs_in_non_training_grp.append(user)
                break
    
    log.info(
        "found {n} new account requests that have already been added to a non training project (excluding {excluded})".format(
            n=len(new_act_reqs),
            excluded=exclude
        )
    )

    return new_act_reqs_in_non_training_grp

if __name__=="__main__":
    pass