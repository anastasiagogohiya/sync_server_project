import pytest
from unittest.mock import MagicMock, patch
from src import main

TEST_TOKEN = "test_token"
TEST_CLOUD_FOLDER = "/test_cloud"
TEST_SYNC_FOLDER = "/local/sync"
TEST_PERIOD = 5


@pytest.fixture(autouse=True)
def mock_config(monkeypatch):
    monkeypatch.setattr("src.main.TOKEN", TEST_TOKEN)
    monkeypatch.setattr("src.main.CLOUD_FOLDER", TEST_CLOUD_FOLDER)
    monkeypatch.setattr("src.main.SYNC_FOLDER", TEST_SYNC_FOLDER)
    monkeypatch.setattr("src.main.PERIOD_OF_SYNC", TEST_PERIOD)


@pytest.fixture
def mock_logger():
    with patch("src.main.logger") as mock:
        yield mock


@pytest.fixture
def mock_yandex_disk():
    with patch("src.main.YandexDisk") as mock_class:
        instance = MagicMock()
        mock_class.return_value = instance
        yield mock_class, instance


@pytest.fixture
def mock_file_monitoring():
    with patch("src.main.FileMonitoring") as mock_class:
        instance = MagicMock()
        instance.get_files_state.return_value = {"initial": "state"}
        instance.cache_cloud_files.return_value = None
        instance.mirror_sync.return_value = None
        instance.sync.return_value = None
        mock_class.return_value = instance
        yield mock_class, instance


@pytest.fixture
def mock_schedule():
    """Мок для модуля schedule, поддерживающий синтаксис every(...).seconds.do(...)."""
    with patch("src.main.schedule") as mock:
        # Настраиваем цепочку: schedule.every(PERIOD).seconds.do(job)
        mock_job = MagicMock()
        # seconds — атрибут, поэтому не вызываем его как функцию
        mock.every.return_value.seconds.do.return_value = mock_job
        yield mock, mock_job


def test_main_successful_flow(
    mock_logger, mock_yandex_disk, mock_file_monitoring, mock_schedule
):
    mock_schedule_instance, _ = mock_schedule
    _, mock_fm_instance = mock_file_monitoring
    mock_yd_class, mock_yd_instance = mock_yandex_disk

    # Сохраняем переданную в schedule.do функцию job
    saved_job = None

    def do_side_effect(job_func):
        nonlocal saved_job
        saved_job = job_func
        return MagicMock()

    # Применяем side_effect к методу do
    mock_schedule_instance.every.return_value.seconds.do.side_effect = do_side_effect

    # При каждом вызове schedule.run_pending() выполняем сохранённую job и выходим
    def run_pending_side_effect():
        if saved_job is not None:
            saved_job()
        raise KeyboardInterrupt
    mock_schedule_instance.run_pending.side_effect = run_pending_side_effect

    main.main()

    # Проверки
    mock_yd_class.assert_called_once_with(TEST_TOKEN, TEST_CLOUD_FOLDER)
    main.FileMonitoring.assert_called_once_with(
        mock_yd_instance, TEST_SYNC_FOLDER, TEST_CLOUD_FOLDER
    )
    mock_fm_instance.cache_cloud_files.assert_called_once()
    mock_fm_instance.mirror_sync.assert_called_once()
    mock_fm_instance.get_files_state.assert_called_once()

    # Проверяем настройку планировщика
    mock_schedule_instance.every.assert_called_once_with(TEST_PERIOD)
    # seconds — атрибут, не вызывается, проверяем только вызов do
    mock_schedule_instance.every.return_value.seconds.do.assert_called_once()

    mock_logger.debug.assert_any_call("Программа остановлена пользователем.")


def test_main_mirror_sync_raises_storage_error(
    mock_logger, mock_yandex_disk, mock_file_monitoring, mock_schedule
):
    _, mock_fm_instance = mock_file_monitoring
    mock_fm_instance.mirror_sync.side_effect = main.StorageError("Mirror sync failed")

    mock_schedule_instance, _ = mock_schedule
    mock_schedule_instance.run_pending.side_effect = KeyboardInterrupt

    main.main()

    mock_fm_instance.mirror_sync.assert_called_once()
    mock_logger.error.assert_called_with(
        "Ошибка во время первой зеркальной синхронизации: Mirror sync failed"
    )
    mock_fm_instance.cache_cloud_files.assert_called_once()
    mock_fm_instance.get_files_state.assert_called_once()


def test_job_calls_sync_and_handles_error(
    mock_logger, mock_yandex_disk, mock_file_monitoring, mock_schedule
):
    _, mock_fm_instance = mock_file_monitoring
    mock_schedule_instance, _ = mock_schedule

    saved_job = None

    def do_side_effect(job_func):
        nonlocal saved_job
        saved_job = job_func
        return MagicMock()

    mock_schedule_instance.every.return_value.seconds.do.side_effect = do_side_effect

    # Выходим из цикла сразу, не вызывая job через run_pending
    mock_schedule_instance.run_pending.side_effect = KeyboardInterrupt

    main.main()

    assert saved_job is not None, "Функция job не была сохранена"

    # Первый вызов: успешная синхронизация
    saved_job()
    mock_fm_instance.sync.assert_called_once()

    # Проверка обработки ошибки
    mock_fm_instance.sync.reset_mock()
    mock_logger.error.reset_mock()
    mock_fm_instance.sync.side_effect = main.StorageError("Sync error")
    saved_job()

    mock_fm_instance.sync.assert_called_once()
    mock_logger.error.assert_called_once_with("Ошибка во время синхронизации: Sync error")


def test_keyboard_interrupt_logging(
    mock_logger, mock_yandex_disk, mock_file_monitoring, mock_schedule
):
    mock_schedule_instance, _ = mock_schedule
    mock_schedule_instance.run_pending.side_effect = KeyboardInterrupt
    main.main()
    mock_logger.debug.assert_called_with("Программа остановлена пользователем.")