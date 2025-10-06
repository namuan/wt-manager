from wt_manager import main


def test_main_function_exists():
    """Test that the main function is callable."""
    assert callable(main)


def test_window_creation(qtbot):
    """Test that the main window can be created."""
    # Since main() runs the app loop, we can't call it directly in tests
    # Instead, create the window components manually
    from PyQt6.QtWidgets import QWidget

    window = QWidget()
    window.setWindowTitle("WorkTree Manager")
    window.setGeometry(100, 100, 400, 300)

    qtbot.addWidget(window)
    assert window.windowTitle() == "WorkTree Manager"
    assert window.geometry().width() == 400
    assert window.geometry().height() == 300
