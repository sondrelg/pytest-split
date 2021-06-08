import itertools
import json
import os

import pytest

pytest_plugins = ["pytester"]


@pytest.fixture
def example_suite(testdir):
    testdir.makepyfile("".join(f"def test_{num}(): pass\n" for num in range(1, 11)))
    yield testdir


@pytest.fixture
def durations_path(tmpdir):
    return str(tmpdir.join(".durations"))


class TestStoreDurations:
    def test_it_stores(self, example_suite, durations_path):
        example_suite.runpytest("--store-durations", "--durations-path", durations_path)

        with open(durations_path) as f:
            durations = json.load(f)

        assert list(durations.keys()) == [
            "test_it_stores.py::test_1",
            "test_it_stores.py::test_2",
            "test_it_stores.py::test_3",
            "test_it_stores.py::test_4",
            "test_it_stores.py::test_5",
            "test_it_stores.py::test_6",
            "test_it_stores.py::test_7",
            "test_it_stores.py::test_8",
            "test_it_stores.py::test_9",
            "test_it_stores.py::test_10",
        ]

        for duration in durations.values():
            assert isinstance(duration, float)

    def test_it_does_not_store_without_flag(self, example_suite, durations_path):
        example_suite.runpytest("--durations-path", durations_path)
        assert not os.path.exists(durations_path)


class TestSplitToSuites:
    @pytest.mark.parametrize(
        "param_idx, splits, expected_tests_per_group",
        [
            (
                0,
                1,
                [
                    [
                        "test_1",
                        "test_2",
                        "test_3",
                        "test_4",
                        "test_5",
                        "test_6",
                        "test_7",
                        "test_8",
                        "test_9",
                        "test_10",
                    ]
                ],
            ),
            (
                1,
                2,
                [
                    ["test_1", "test_2", "test_3", "test_4", "test_5", "test_6", "test_7"],
                    ["test_8", "test_9", "test_10"],
                ],
            ),
            (
                2,
                3,
                [
                    ["test_1", "test_2", "test_3", "test_4", "test_5", "test_6"],
                    ["test_7", "test_8", "test_9"],
                    ["test_10"],
                ],
            ),
            (
                3,
                4,
                [
                    ["test_1", "test_2", "test_3", "test_4"],
                    ["test_5", "test_6", "test_7"],
                    ["test_8", "test_9"],
                    ["test_10"],
                ],
            ),
        ],
    )
    def test_it_splits(self, param_idx, splits, expected_tests_per_group, example_suite, durations_path):
        assert len(list(itertools.chain(*expected_tests_per_group))) == 10

        durations = {
            "test_it_splits{}/test_it_splits.py::test_1".format(param_idx): 1,
            "test_it_splits{}/test_it_splits.py::test_2".format(param_idx): 1,
            "test_it_splits{}/test_it_splits.py::test_3".format(param_idx): 1,
            "test_it_splits{}/test_it_splits.py::test_4".format(param_idx): 1,
            "test_it_splits{}/test_it_splits.py::test_5".format(param_idx): 1,
            "test_it_splits{}/test_it_splits.py::test_6".format(param_idx): 2,
            "test_it_splits{}/test_it_splits.py::test_7".format(param_idx): 2,
            "test_it_splits{}/test_it_splits.py::test_8".format(param_idx): 2,
            "test_it_splits{}/test_it_splits.py::test_9".format(param_idx): 2,
            "test_it_splits{}/test_it_splits.py::test_10".format(param_idx): 2,
        }

        with open(durations_path, "w") as f:
            json.dump(durations, f)

        results = [
            example_suite.inline_run(
                "--splits",
                str(splits),
                "--group",
                str(group + 1),
                "--durations-path",
                durations_path,
            )
            for group in range(splits)
        ]

        for result, expected_tests in zip(results, expected_tests_per_group):
            result.assertoutcome(passed=len(expected_tests))
            assert _passed_test_names(result) == expected_tests

    def test_it_does_not_split_with_invalid_args(self, example_suite, durations_path):
        durations = {"test_it_does_not_split_with_invalid_args.py::test_1": 1}
        with open(durations_path, "w") as f:
            json.dump(durations, f)

        # Plugin doesn't run when splits is passed but group is missing
        result = example_suite.inline_run("--splits", "2", "--durations-path", durations_path)  # no --group
        result.assertoutcome(passed=10)

        # Plugin doesn't run when group is passed but splits is missing
        result = example_suite.inline_run("--group", "2", "--durations-path", durations_path)  # no --splits
        result.assertoutcome(passed=10)

        # Runs if they both are
        result = example_suite.inline_run("--splits", "2", "--group", "1")
        result.assertoutcome(passed=6)

    def test_it_adapts_splits_based_on_new_and_deleted_tests(self, example_suite, durations_path):
        # Only 4/10 tests listed here, avg duration 1 sec
        test_path = (
            "test_it_adapts_splits_based_on_new_and_deleted_tests0/"
            "test_it_adapts_splits_based_on_new_and_deleted_tests.py::{}"
        )
        durations = {
            test_path.format("test_1"): 1,
            test_path.format("test_5"): 2.6,
            test_path.format("test_6"): 0.2,
            test_path.format("test_10"): 0.2,
            test_path.format("test_THIS_IS_NOT_IN_THE_SUITE"): 1000,
        }

        with open(durations_path, "w") as f:
            json.dump(durations, f)

        result = example_suite.inline_run("--splits", "3", "--group", "1", "--durations-path", durations_path)
        result.assertoutcome(passed=4)
        assert _passed_test_names(result) == ["test_1", "test_2", "test_3", "test_4"]

        result = example_suite.inline_run("--splits", "3", "--group", "2", "--durations-path", durations_path)
        result.assertoutcome(passed=3)
        assert _passed_test_names(result) == ["test_5", "test_6", "test_7"]

        result = example_suite.inline_run("--splits", "3", "--group", "3", "--durations-path", durations_path)
        result.assertoutcome(passed=3)
        assert _passed_test_names(result) == [
            "test_8",
            "test_9",
            "test_10",
        ]


def _passed_test_names(result):
    return [passed.nodeid.split("::")[-1] for passed in result.listoutcomes()[0]]


def test_setup_time_is_not_recorded(testdir, durations_path):
    testdir.makepyfile(
        """
        import pytest
        import time

        @pytest.fixture(autouse=True, scope="session")
        def slow_start():
            time.sleep(5)

        def test_something():
            time.sleep(1)

        def test_something_else():
            time.sleep(1)
        """
    )
    testdir.inline_run("--store-durations", "--durations-path", durations_path)
    with open(durations_path, "r") as f:
        durations = json.load(f)
        
    for duration in durations.values():
        assert duration < 2
