import pytest

from generate_user_report import get_new_account_requests
from generate_user_report import get_new_accounts_accepted
from generate_user_report import get_new_accounts_accepted_in_training_group
from generate_user_report import get_new_accounts_accepted_in_non_training_group

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
    def test_dump_snapshot(self):
        pass
    
    def test_get_new_account_requests(self, prev_snapshot, curr_snapshot):
        result = get_new_account_requests(prev_snapshot, curr_snapshot)
        assert result == ["pam_beesly"]
    
        assert result == ["pam_beesly"]
    
    def test_get_new_accounts_accepted(self, prev_snapshot, curr_snapshot):
        result = get_new_accounts_accepted(prev_snapshot, curr_snapshot)
        assert result == ["jim_halpert"]

    @pytest.mark.parametrize(
        "curr_snapshot, expected_result",
        [
            (
                {
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
                        }
                    }
                },
                ["jim_halpert"]
            ),
            (
                {
                    "date": "2021-Jan-07 00:00:00.000000 UTC",
                    "users": {
                        "jim_halpert": {
                            "osg_state": "active",
                            "join_date": "2021-Jan-01 00:00:00.000000 UTC",
                            "groups": {
                                "root.osg": "active",
                                "root.osg.non_training": "active"
                            }
                        }
                    }
                },
                [] 
            )
        ]
    )
    def test_get_new_accounts_accepted_in_training_group(self, curr_snapshot, expected_result):
        result = get_new_accounts_accepted_in_training_group(
            new_acts_accepted=["jim_halpert"],
            curr_snapshot=curr_snapshot,
            training_projects={"root.osg.training2021"}
        )

        assert result == expected_result
    
    @pytest.mark.parametrize(
        "curr_snapshot, exclude, training_groups, expected_result",
        [
            (
                {
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
                        }
                    }
                },
                {"root", "root.osg"},
                {"root.osg.training2021"},
                ["jim_halpert"]
            ),
            (
                {
                    "date": "2021-Jan-07 00:00:00.000000 UTC",
                    "users": {
                        "jim_halpert": {
                            "osg_state": "active",
                            "join_date": "2021-Jan-01 00:00:00.000000 UTC",
                            "groups": {
                                "root.osg": "active",
                                "root.osg.training2021": "active",
                            }
                        }
                    }
                },
                {"root", "root.osg"},
                {"root.osg.training2021"},
                []
            ),
            (
                {
                    "date": "2021-Jan-07 00:00:00.000000 UTC",
                    "users": {
                        "jim_halpert": {
                            "osg_state": "active",
                            "join_date": "2021-Jan-01 00:00:00.000000 UTC",
                            "groups": {
                                "root.osg": "active",
                                "root.osg.training2021": "active",
                                "root.osg.non_training": "pending"
                            }
                        }
                    }
                },
                {"root", "root.osg"},
                {"root.osg.training2021"},
                ["jim_halpert"]
            )
        ]
    )
    def test_get_new_accepted_in_non_training_group(
            self, 
            curr_snapshot, 
            exclude,
            training_groups,
            expected_result
        ):
        result = get_new_accounts_accepted_in_non_training_group(
            new_acts_accepted=["jim_halpert"],
            curr_snapshot=curr_snapshot,
            training_projects={"root.osg.training2021"},
            exclude=exclude
        )

        assert result == expected_result
