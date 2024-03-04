import uuid
import shutil

from flask_apscheduler import APScheduler
import os

from visualization.mixed_traffic_scenario import generate_embeddable_html_snippet
from controller.internalav import drive

from apscheduler.jobstores.base import JobLookupError
from apscheduler.schedulers.base import STATE_RUNNING
from apscheduler.events import EVENT_JOB_ERROR

from datetime import datetime, timedelta, timezone

from model.mixed_traffic_scenario import MixedTrafficScenario, MixedTrafficScenarioStatusEnum
from model.driver import Driver
from model.vehicle_state import VehicleState

from sqlalchemy import orm

# initialize the global scheduler
scheduler = APScheduler()

def init_app(app):
    """
    Init the scheduler
    """
    app.logger.debug("Initialize Background Scheduler")
    scheduler.init_app(app)

    if "AVS_CACHE_FOLDER" in app.config and not os.path.exists(app.config["AVS_CACHE_FOLDER"]):
        app.logger.debug(f"Create AVS cache folder at {app.config['AVS_CACHE_FOLDER']}")
        os.makedirs(app.config["AVS_CACHE_FOLDER"], exist_ok=True)

    scheduler.start()
    print(f"Initialize Background Scheduler {scheduler}")

    def listener(event):
        if str(event.job_id).startswith("Driver_"):
            # print(f'Driver Job {event.job_id} raised {event.exception.__class__.__name__}')
            if event.exception.__class__.__name__ == "StopMeException":
                # run_date = datetime.now(timezone.utc) + timedelta(seconds=3)
                # https://viniciuschiele.github.io/flask-apscheduler/rst/api.html
                # scheduler.modify_job(event.job_id, trigger="date", run_date=run_date )
                scheduler.remove_job(event.job_id)
                print(f'Driver Job {event.job_id} stopped')

        else:
            print(f'Rendering Job {event.job_id} raised {event.exception.__class__.__name__}')


    scheduler.add_listener(listener, EVENT_JOB_ERROR)

# Note: We do not automatically resume the jobs to rendere png and similar.
# We'll do that "on the fly" in case some image is still missing
# Otherwise, we need to compute what are the ACTIVE states in ALL the SCENARIOS, check that
# they are not present in anyform inside the scenario_images folder and generate them.
# TODO This actually might be something to do always? Lazily generate the images ?

def rewamp_jobs(scenario=None):
    # TODO When we deploy in uWSGI, it will creates many different copies of this code, thus running many
    #   schedulers that are independent. So all of them will try to respawn all the jobs. Assuming we know how many
    #   of such processes exist (e.g., configuration) we can split and distribute the load on restart!
    #

    # Avoid circular deps
    from persistence.mixed_scenario_data_access import MixedTrafficScenarioDAO
    from views.authentication import create_the_token

    scenario_dao = MixedTrafficScenarioDAO(scheduler.app.config)

    if scenario is None:
        # When we invoke this at app restart, so we need to enforce a context. Also, we resume the AVs of all the scenarios
        with scheduler.app.app_context():
            # Do the simplest thing, we might push this back to DB if needed
            active_scenarios = scenario_dao.get_all_scenarios(status="ACTIVE")
            # We should not rewamp on WAITING scenarios, or the AVs will just wakeup and then stop again
            # waiting_scenarios = scenario_dao.get_all_scenarios(status="WAITING")
            # Extract all the bots and restart them
            for scenario in active_scenarios:
                for driver in scenario.drivers:
                    # Some drivers might still without a user. Do they? this is not a WAITING scenario anymore...
                    if driver.user and driver.user.username.startswith("bot_"):
                        try:
                            # Generate a pseudo-new token
                            token = create_the_token(driver.user)
                            # (Re)Start the AV
                            deploy_av_in_background(driver, token)
                        except AssertionError as ex_info:
                            # Because in production we cannot control the parallel processes executing this code
                            # it happens that more than the same AV is started more than one time, causing consistency issues
                            # in the DB.
                            # TODO Check that ex_info is the expected one, otherwise bubble up the exception
                            print(f"Failed to (re)start AV {driver.user.username} - reason {ex_info.args}")
    else:
        # We do not enforce a context and we focus ONLY on the given scenario.
        if scenario.status == MixedTrafficScenarioStatusEnum.ACTIVE:
            for driver in scenario.drivers:
                # Some drivers might still without a user. Do they? this is not a WAITING scenario anymore...
                if driver.user and driver.user.username.startswith("bot_"):
                    try:
                        # Generate a pseudo-new token
                        token = create_the_token(driver.user)
                        # (Re)Start the AV
                        deploy_av_in_background(driver, token)
                    except AssertionError as ex_info:
                        # Because in production we cannot control the parallel processes executing this code
                        # it happens that more than the same AV is started more than one time, causing consistency issues
                        # in the DB.
                        # TODO Check that ex_info is the expected one, otherwise bubble up the exception
                        print(f"Failed to (re)start AV {driver.user.username} - reason {ex_info.args}")

def _eager_load_scenario(scenario: MixedTrafficScenario):
    # TODO Not sure how to avoid using the query object
    return MixedTrafficScenario.query.options(
        orm.joinedload(MixedTrafficScenario.owner),
        orm.joinedload(MixedTrafficScenario.drivers),
        orm.joinedload(MixedTrafficScenario.scenario_template)
    ).where(MixedTrafficScenario.scenario_id == scenario.scenario_id).first()

def _eager_load_driver(driver: Driver):
    return Driver.query.options(
        orm.joinedload(Driver.scenario),
        orm.joinedload(Driver.user)
    ).where(Driver.driver_id == driver.driver_id).first()


def _eager_load_scenario_state(vehicle_state: VehicleState):
    return VehicleState.query.where(VehicleState.vehicle_state_id == vehicle_state.vehicle_state_id).first()


def get_job_id(driver):
    return f"Driver_{driver.driver_id}"


def _get_rendering_job_id(mixed_traffic_scenario_scenario_id, scenario_state, focus_on_driver_user_id):
    if focus_on_driver_user_id:
        return f"Rendering_scenario_{mixed_traffic_scenario_scenario_id}_timestamp_{scenario_state[0].timestamp}_driver_{focus_on_driver_user_id}"
    else:
        return f"Rendering_scenario_{mixed_traffic_scenario_scenario_id}_timestamp_{scenario_state[0].timestamp}"


# THIS IS PROBLEMATIC BECAUSE WE HAVE NO IDEA WHERE THE JOB MIGHT BE RUNNING!
def undeploy_av(driver):
    pass

    # job_id = get_job_id(driver)
    # try:
    #     scheduler.remove_job(id=job_id)
    #     scheduler.app.logger.debug(f"Background AV Driving removed for user {driver.user_id} in scenario {driver.scenario_id}. Job id: {job_id}")
    #     if "AVS_CACHE_FOLDER" in scheduler.app.config and os.path.exists(scheduler.app.config["AVS_CACHE_FOLDER"]):
    #         # Remove the cache only if we are NOT in testing
    #         if not scheduler.app.config["TESTING"]:
    #             try:
    #                 scheduler.app.logger.debug(f"Removing cached data for {driver.driver_id}")
    #                 shutil.rmtree(os.path.join(scheduler.app.config["AVS_CACHE_FOLDER"], f"av_driver_{driver.driver_id}"))
    #             except Exception:
    #                 scheduler.app.logger.debug(f"Problem removing cached data for {driver.driver_id}")
    #
    #
    # except JobLookupError as e:
    #     scheduler.app.logger.debug(
    #         f"Background AV Driving user {driver.user_id} in scenario {driver.scenario_id} is not running.")


def deploy_av_in_background(driver, auth_token):
    """
    Deploy a new AV in background. This job takes the scheduler and reschedule itself after X seconds if necessary

    :param mixed_traffic_scenario:
    :param user:
    :param driver:
    :return:
    """

    assert driver.user_id, "Cannot deploy a driver without a User ID"
    assert driver.user, "Cannot deploy a driver without a User"
    assert driver.scenario_id, "Cannot deploy a driver without a Scenario"
    # TODO Remove this in the next future
    assert driver.user.username.startswith("bot_"), "Cannot deploy a non AV driver"

    if scheduler.state == STATE_RUNNING:
        cache_dir = scheduler.app.config["AVS_CACHE_FOLDER"] if "AVS_CACHE_FOLDER" in scheduler.app.config else None

        # The job ID is the unique id of the Driver
        job_id = get_job_id(driver)

        args = [driver.driver_id, driver.user_id, driver.scenario_id, auth_token, cache_dir]

        # Patch because the port is not available inside current_app.config natively
        kwargs = {
            "port": scheduler.app.config["PORT"] if "PORT" in scheduler.app.config else 5000
        }

        scheduler.app.logger.info(
            f'Listening to port {scheduler.app.config["PORT"] if "PORT" in scheduler.app.config else 5000}')

        # scheduler.add_job(id=INTERVAL_TASK_ID, func=interval_task, trigger='interval', seconds=2)
        run_date = datetime.now(timezone.utc) + timedelta(seconds=3)
        job = scheduler.add_job(
            job_id,
            drive,
            # trigger = 'date',
            # run_date= run_date,
            # misfire_grace_time = None,
            trigger='interval',
            seconds=3,
            executor="driving",
            replace_existing=False,
            args=args,
            kwargs=kwargs
        )
        print(f">>>> Background AV Driving will start in {run_date - datetime.now(timezone.utc)})."
              f"User {driver.user_id} in scenario {driver.scenario_id}. Job id: {job_id} - {job.id}")
    else:
        scheduler.app.logger.error("Cannot deploy AV if the scheduler is not running!")




def render_in_background(output_folder, mixed_traffic_scenario, scenario_state,
                                     focus_on_driver=None, goal_region_as_rectangle=None,
                                     force_render_now = False):

    # Convert to the new parameters:
    commonroad_scenario = mixed_traffic_scenario.scenario_template.as_commonroad_scenario()
    mixed_traffic_scenario_duration = mixed_traffic_scenario.duration
    mixed_traffic_scenario_scenario_id = mixed_traffic_scenario.scenario_id

    args = []
    args.append(output_folder)
    args.append(commonroad_scenario)
    args.append(mixed_traffic_scenario_duration)
    args.append(mixed_traffic_scenario_scenario_id)

    # Transform the states in plain objects with the same attributes!
    args.append([s.as_plain_state() for s in scenario_state])

    kwargs = {}
    if focus_on_driver is not None:
        focus_on_driver_user_id = focus_on_driver.user_id
        kwargs["focus_on_driver_user_id"] = focus_on_driver_user_id
    else:
        focus_on_driver_user_id = None

    if goal_region_as_rectangle is not None:
        kwargs["goal_region_as_rectangle"] = goal_region_as_rectangle

    # Schedule it (now). Probably better to generate a place holder image first and then replace it with the actual one...?
    # https://viniciuschiele.github.io/flask-apscheduler/rst/usage.html
    # https://apscheduler.readthedocs.io/en/3.x/modules/triggers/date.html#module-apscheduler.triggers.date

    job_id = _get_rendering_job_id(mixed_traffic_scenario_scenario_id, scenario_state, focus_on_driver_user_id)

    if scheduler.state == STATE_RUNNING and not force_render_now:
        job = scheduler.add_job(
            id=job_id,
            executor="rendering",
            func=generate_embeddable_html_snippet,
            replace_existing=False,
            args=args,
            kwargs=kwargs,
            misfire_grace_time=30
        )
        print(f">>> Background rendering started. Job id: {job.id} - {job_id}")
        scheduler.app.logger.debug(f">>> Background rendering started. Job id: {job.id} - {job_id}")
    else:
        print(f">>> Direct rendering started. Job id: {job_id}")
        # Invoke it directly in case the scheduler does is not running
        generate_embeddable_html_snippet(*args, **kwargs)
