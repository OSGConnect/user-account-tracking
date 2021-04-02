import pytest

from generate_user_report import get_new_account_requests
from generate_user_report import get_new_account_requests_in_training_group
from generate_user_report import get_new_account_requests_in_non_training_group

@pytest.fixture
def prev_snapshot():
    return {
                "date": "2021-Jan-01 00:00:01.000000 UTC",
                "users": {
                    "jim_halpert": {
                        "osg_state": "pending",
                        "join_date": "2021-Jan-01 00:00:00.000000 UTC",
                        "groups": {
                            "root.osg": "pending",
                            "root.osg.training2021": "pending",
                            "root.osg.non_training": "pending"
                        }
                    },
                    "pam_beesly": {
                        "osg_state": "active",
                        "join_date": "2021-Jan-01 04:46:25.868712 UTC",
                        "groups": {
                            "root.osg": "active",
                            "root.osg.non_training": "active"
                        }
                    }
                }
            }

@pytest.fixture
def curr_snapshot():
    return {
                "date": "2021-Jan-07 00:00:00.000000 UTC",
                "users": {
                    "jim_halpert": {
                        "osg_state": "active",
                        "join_date": "2021-Jan-01 00:00:00.000000 UTC",
                        "groups": {
                            "root.osg": "active",
                            "root.osg.training2021": "active",
                            "root.osg.non_training": "active"
                        }
                    },
                    "pam_beesly": {
                        "osg_state": "active",
                        "join_date": "2021-Jan-01 04:46:25.868712 UTC",
                        "groups": {
                            "root.osg": "active",
                            "root.osg.non_training": "active",
                            "root.osg.training2021": "pending"
                        }
                    }
                }
            }

class TestGetNewAccountRequests:
    def test_get_new_account_requests(self, prev_snapshot, curr_snapshot):
        new_act_req = get_new_account_requests(prev_snapshot, curr_snapshot)
        assert new_act_req == ["pam_beesly"]
    
    def test_get_new_account_requests_in_training_group(self, curr_snapshot):
        new_act_reqs_in_training_grp = get_new_account_requests_in_training_group(
            new_act_reqs=["pam_beesly"],
            curr_snapshot=curr_snapshot,
            training_projects={"root.osg.training2021"}
        )

        assert new_act_reqs_in_training_grp == ["pam_beesly"]
    
    def test_get_new_account_requests_in_non_training_group(self, curr_snapshot):
        new_act_reqs_in_non_training_grp = get_new_account_requests_in_non_training_group(
            new_act_reqs=["pam_beesly"],
            curr_snapshot=curr_snapshot,
            training_projects={"root.osg.training2021"},
        )

        assert new_act_reqs_in_non_training_grp == ["pam_beesly"]
