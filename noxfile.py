import nox  # type: ignore[import]


@nox.session(python=False)
def run(session):
    session.run("python", "main.py")


@nox.session
def tests(session):
    session.install("-r", "requirements.txt", "-r", "requirements-dev.txt")
    session.run("pytest")


@nox.session
def lint(session):
    session.install("ruff", "black")
    session.run("ruff", "check", ".")
    session.run("black", "--check", ".")


@nox.session
def format(session):
    session.install("black")
    session.run("black", ".")


@nox.session
def typecheck(session):
    session.install("mypy")
    session.run("mypy", "src")


@nox.session
def dev(session):
    """소스 변경 시 자동 재실행(Hot restart)."""
    session.install("-r", "requirements.txt", "-r", "requirements-dev.txt")
    session.install("watchfiles")
    session.run("python", "-m", "watchfiles", "python main.py", "src", external=True)


@nox.session
def test_watch(session):
    """테스트 자동 재실행."""
    session.install("-r", "requirements.txt", "-r", "requirements-dev.txt")
    session.install("pytest-watch")
    session.run("ptw", "-q", external=True)


