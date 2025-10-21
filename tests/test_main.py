import sys
from pathlib import Path
import pytest
from unittest import mock
import importlib
from app.main import (
    create_directory,
    is_valid_url,
    generate_qr_code,
    setup_logging,
    main,
    QR_DIRECTORY,
    FILL_COLOR,
    BACK_COLOR,
)

# Initialize logging so caplog works
setup_logging()


# ---------------- is_valid_url ----------------
@pytest.mark.parametrize(
    "url,expected",
    [
        ("http://127.0.0.1:8000", True),            # IP with port
        ("https://", False),                        # incomplete scheme
        ("https://example", False),                 # no domain suffix
        ("https://user:pass@domain.com", True),     # auth in URL
        ("http://?query=param", False),             # no hostname
        ("https://toolong" + "a"*5000 + ".com", False),  # absurdly long URL
    ]
)
def test_is_valid_url_edge_cases(url, expected):
    assert is_valid_url(url) == expected


# ---------------- create_directory ----------------
@pytest.mark.parametrize("make_fail", [False, True])
def test_create_directory(tmp_path, make_fail):
    dir_path = tmp_path / "newdir"

    if make_fail:
        with mock.patch("pathlib.Path.mkdir", side_effect=Exception("fail")):
            with pytest.raises(SystemExit):
                create_directory(dir_path)
    else:
        create_directory(dir_path)
        assert dir_path.exists() and dir_path.is_dir()

@pytest.mark.parametrize("exists_before", [True, False])
def test_create_directory_exists_and_permissions(tmp_path, exists_before):
    dir_path = tmp_path / "existing"

    if exists_before:
        dir_path.mkdir()
    with mock.patch("pathlib.Path.mkdir", side_effect=PermissionError("no perm")):
        with pytest.raises(SystemExit):
            create_directory(dir_path)

def test_create_directory_race_condition(tmp_path):
    dir_path = tmp_path / "concurrent"
    dir_path.mkdir()
    # mkdir() should not crash if directory already exists
    create_directory(dir_path)



# ---------------- generate_qr_code ----------------
@pytest.mark.parametrize(
    "url,expect_file,expect_log",
    [
        ("https://github.com/mihirkadam19", True, None),
        ("https://openai.com", True, None),
        ("notaurl", False, "Invalid URL provided: notaurl"),
    ]
)
def test_generate_qr_code(tmp_path, caplog, url, expect_file, expect_log):
    qr_path = tmp_path / "qr.png"
    generate_qr_code(url, qr_path, FILL_COLOR, BACK_COLOR)
    assert qr_path.exists() == expect_file
    if expect_log:
        assert expect_log in caplog.text


@pytest.mark.parametrize("exception_type", [IOError, PermissionError])
def test_generate_qr_code_exception(tmp_path, caplog, exception_type):
    qr_path = tmp_path / "qr.png"
    url = "https://github.com/mihirkadam19"

    with mock.patch("pathlib.Path.open", side_effect=exception_type("write error")):
        generate_qr_code(url, qr_path)
    assert "An error occurred while generating or saving the QR code" in caplog.text

@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/?q=こんにちは",     # Unicode
        "https://example.com/?x=<script>",       # special chars
    ]
)
def test_generate_qr_code_special_urls(tmp_path, url):
    qr_path = tmp_path / "qr.png"
    generate_qr_code(url, qr_path)
    assert qr_path.exists()


def test_generate_qr_code_overwrite(tmp_path):
    qr_path = tmp_path / "qr.png"
    generate_qr_code("https://test1.com", qr_path)
    size1 = qr_path.stat().st_size
    generate_qr_code("https://test2.com", qr_path)
    size2 = qr_path.stat().st_size
    assert size1 != size2  # new content overwrote previous file


def test_generate_qr_code_invalid_path(caplog):
    invalid_path = Path("/root/forbidden/qr.png")
    generate_qr_code("https://example.com", invalid_path)
    assert "An error occurred while generating or saving the QR code" in caplog.text



# ---------------- main() CLI ----------------
@pytest.mark.parametrize(
    "cli_url",
    ["https://example.com", "https://github.com/mihirkadam19"]
)
def test_main_cli(monkeypatch, tmp_path, cli_url):
    monkeypatch.setattr(sys, "argv", ["prog", "--url", cli_url])
    monkeypatch.setattr("pathlib.Path.cwd", lambda: tmp_path)

    main()

    qr_dir = tmp_path / "qr_codes"  # QR_DIRECTORY default
    files = list(qr_dir.glob("*.png"))
    assert files, "QR code file should be created by main()"

def test_main_invalid_url(monkeypatch, tmp_path, caplog):
    monkeypatch.setattr(sys, "argv", ["prog", "--url", "notaurl"])
    monkeypatch.setattr("pathlib.Path.cwd", lambda: tmp_path)
    main()
    assert "Invalid URL provided" in caplog.text


def test_main_directory_creation_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["prog", "--url", "https://example.com"])
    with mock.patch("pathlib.Path.mkdir", side_effect=OSError("fail")):
        with pytest.raises(SystemExit):
            main()


# ---------------- Environment variables ----------------
@pytest.mark.parametrize(
    "fill_color, back_color, expected_fill, expected_back",
    [
        (None, None, "red", "white"),          # defaults
        ("blue", "yellow", "blue", "yellow"),  # custom
    ]
)
def test_env_colors(monkeypatch, fill_color, back_color, expected_fill, expected_back):
    if fill_color:
        monkeypatch.setenv("FILL_COLOR", fill_color)
    else:
        monkeypatch.delenv("FILL_COLOR", raising=False)

    if back_color:
        monkeypatch.setenv("BACK_COLOR", back_color)
    else:
        monkeypatch.delenv("BACK_COLOR", raising=False)

    from app import main as main_module
    importlib.reload(main_module)  # Reload to pick up new env vars

    assert main_module.FILL_COLOR == expected_fill
    assert main_module.BACK_COLOR == expected_back


@pytest.mark.parametrize(
    "fill,back",
    [
        ("", ""),               # empty
        ("#123456", "#ffffff"), # hex colors
        ("123", "456"),         # invalid format but strings
    ]
)
def test_env_colors_invalid(monkeypatch, fill, back):
    monkeypatch.setenv("FILL_COLOR", fill)
    monkeypatch.setenv("BACK_COLOR", back)
    import app.main as main_module
    importlib.reload(main_module)
    assert isinstance(main_module.FILL_COLOR, str)
    assert isinstance(main_module.BACK_COLOR, str)



@pytest.mark.parametrize(
    "env_value,expected_dir",
    [
        ("custom_qr_dir", "custom_qr_dir"),   # custom directory via env
        ("", ""),                     # empty string → fallback to default
        (None, "qr_codes"),                   # env var not set → default
    ]
)
def test_env_qr_directory(monkeypatch, env_value, expected_dir):
    if env_value is not None:
        monkeypatch.setenv("QR_CODE_DIR", env_value)
    else:
        monkeypatch.delenv("QR_CODE_DIR", raising=False)

    import app.main as main_module
    importlib.reload(main_module)
    assert main_module.QR_DIRECTORY == expected_dir