# StudySync

StudySync is a web-based academic resource portal where students can browse and share study notes and materials.

## Tech Stack

| Layer | Technology |
| --- | --- |
| Frontend | React, TypeScript, Vite |
| Backend | Python, FastAPI, Uvicorn |
| Database | Supabase PostgreSQL |
| Authentication | Supabase Auth |
| File Storage | Google Drive |

## Prerequisites

Make sure the following are installed:

- Git
- Python 3.11+
- Node.js 18+
- npm

Check the installed versions.

**macOS / Ubuntu / WSL**

```bash
git --version
python3 --version
node --version
npm --version
```

**Windows**

```powershell
git --version
python --version
node --version
npm --version
```

## Installation

Clone the repository and move into the project directory:

```bash
git clone <repository-url>
cd Study_sync
```

### Backend

1. Move to the backend directory:

   ```bash
   cd backend
   ```

2. Create a Python virtual environment.

   **macOS / Ubuntu / WSL**

   ```bash
   python3.11 -m venv .venv
   ```

   **Windows**

   ```powershell
   py -3.11 -m venv .venv
   ```

3. Activate the virtual environment.

   **macOS / Ubuntu / WSL**

   ```bash
   source .venv/bin/activate
   ```

   **Windows PowerShell**

   ```powershell
   .venv\Scripts\Activate.ps1
   ```

   **Windows Command Prompt**

   ```bat
   .venv\Scripts\activate
   ```

4. Upgrade pip:

   ```bash
   python -m pip install --upgrade pip
   ```

5. Install the backend dependencies:

   ```bash
   pip install -r requirements.txt
   ```

6. Create a `.env` file inside the `backend` directory, using `.env.example` as a reference, and add the required Supabase configuration:

   ```env
   SUPABASE_URL=your_supabase_url
   SUPABASE_ANON_KEY=your_supabase_anon_key
   ```

7. Start the FastAPI server:

   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

The backend will be available at <http://localhost:8000>, and the FastAPI API documentation at <http://localhost:8000/docs>.

### Frontend

1. Open a **new terminal** and move to the frontend directory:

   ```bash
   cd StudySync/frontend
   ```

   > The Python virtual environment is not required for the frontend.

2. Install the Node.js dependencies:

   ```bash
   npm install
   ```

3. If a frontend `.env.example` file is provided, create a `.env` file from it and add the required Supabase configuration:

   ```env
   VITE_SUPABASE_URL=your_supabase_url
   VITE_SUPABASE_ANON_KEY=your_supabase_anon_key
   ```

4. Start the frontend development server:

   ```bash
   npm run dev
   ```

The frontend will be available at <http://localhost:5173>.

## Running the Project

The backend and frontend need to run at the same time, each in its own terminal.

**Terminal 1: Backend**

```bash
cd Study_sync/backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

**Terminal 2: Frontend**

```bash
cd Study_sync/frontend
npm run dev
```

Then open the application in your browser at <http://localhost:5173>.

### Windows PowerShell

Activate the backend environment using:

```powershell
cd Study_sync\backend
.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

The frontend commands stay the same:

```powershell
cd Study_sync\frontend
npm run dev
```

## Project URLs

| Service | URL |
| --- | --- |
| Frontend | <http://localhost:5173> |
| Backend | <http://localhost:8000> |
| FastAPI Docs | <http://localhost:8000/docs> |
| Backend Health Check | <http://localhost:8000/api/health> |


## Python and Node Dependencies

The backend and frontend use separate environments.

- Python dependencies are installed inside `backend/.venv/` using `pip install -r requirements.txt`.
- Frontend dependencies are installed inside `frontend/node_modules/` using `npm install`.

Node.js packages should not be installed inside the Python virtual environment.

## Common Issues

### Python version is too old

Check your Python version:

```bash
python3 --version
```

StudySync requires Python 3.11 or later. If Python 3.11 is installed, create the virtual environment with it:

```bash
python3.11 -m venv .venv
```

### `uvicorn` is not found

Make sure the Python virtual environment is activated:

```bash
source .venv/bin/activate
```

Then install the dependencies again:

```bash
pip install -r requirements.txt
```

You can also run Uvicorn as a module:

```bash
python -m uvicorn app.main:app --reload --port 8000
```

### `npm` is not found

Check your Node.js and npm installation:

```bash
node --version
npm --version
```

Install Node.js if these commands are not available.

### Frontend dependencies are missing

From the `frontend` directory, run:

```bash
npm install
npm run dev
```

### Backend dependencies are missing

Activate the virtual environment, then install the dependencies:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

## Stopping the Project

To stop either development server, press `Ctrl + C` in the corresponding terminal.