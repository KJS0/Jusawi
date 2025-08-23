import nox


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


