import os
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

admin_router = APIRouter(prefix="/admin")


def login_form() -> str:
    return """<!DOCTYPE html>
    <html>
        <head>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                }
                form {
                    display: flex;
                    flex-direction: column;
                    gap: 10px;
                }
                input[type="password"] {
                    padding: 8px;
                }
                button {
                    padding: 8px;
                    cursor: pointer;
                }
            </style>
            <script>
                function handleSubmit(e) {
                    e.preventDefault();
                    const password = document.getElementById('password').value;
                    document.cookie = `admin_password=${password}; path=/; max-age=86400`;
                    window.location.reload();
                }
            </script>
        </head>
        <body>
            <form onsubmit="handleSubmit(event)">
                <input type="password" id="password" placeholder="Admin Password" required>
                <button type="submit">Login</button>
            </form>
        </body>
    </html>
    """


def info(content: str) -> str:
    return f"""<!DOCTYPE html>
    <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                }}
            </style>
        </head>
        <body>
            <div style="text-align: center;">
                {content}
            </div>
        </body>
    </html>
    """

def admin_auth() -> str:
    if os.getenv("ADMIN_PASSWORD", "") == "":
        return info("Please set a secure ADMIN_PASSWORD= in your ENV variables.")
    else:
        return login_form()


def dashboard(request: Request) -> str:
    return info("Admin dashboard")


@admin_router.get("/", response_class=HTMLResponse)
async def admin(request: Request):
    admin_cookie = request.cookies.get("admin_password")
    if admin_cookie and admin_cookie == os.getenv("ADMIN_PASSWORD"):
        return dashboard(request)
    return admin_auth()
