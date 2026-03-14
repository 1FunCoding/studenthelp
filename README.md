# StudentHelp

A full-stack peer tutoring platform where students can post help requests, offer assistance, message each other, and schedule sessions.

## Tech Stack

- **Backend**: Python + Flask + SQLite
- **Frontend**: Vanilla HTML/CSS/JS (single-page app)

## Demo Accounts

| Name  | Email            | Password |
|-------|------------------|----------|
| Nina  | nina@scu.edu     | password |
| Sarah | sarah@scu.edu    | password |
| Mike  | mike@scu.edu     | password |
| Emily | emily@scu.edu    | password |
| Jerry | jerry@scu.edu    | password |

## Setup & Run

```bash
cd studenthelp

# Create a virtual environment and install dependencies
python3 -m venv venv
venv/bin/pip install flask flask-cors

# Start the server (database + demo data seeded automatically on first run)
venv/bin/python app.py
```



## Features

- **Auth** — register, login, logout with role selection (requester / helper / both)
- **Browse** — search and filter open help requests by subject and urgency
- **My Requests** — create, view, and delete your own requests; mark in-progress ones as complete
- **Offer Help** — submit an offer on any request; the offer message is always sent to the shared conversation
- **Messages** — real-time-style messaging with all your contacts (stored in SQLite, polled every 10 s); direct **Message** button on session cards
- **Sessions** — upcoming and past tutoring sessions created when an offer is accepted; either party can mark a session complete
- **Automated messages** — acceptance message sent when an offer is accepted; thank-you message sent when a session is completed
- **Ratings** — requester is prompted to rate the helper immediately after a session is marked complete; notification sent if the helper completes it
- **Notifications** — in-app bell for offer received, offer accepted, new message, and session completed events
- **Profile** — edit your name, bio, and role; view session count and average rating

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/register` | Create account |
| POST | `/api/auth/login` | Login |
| POST | `/api/auth/logout` | Logout |
| GET  | `/api/auth/me` | Get current user |
| GET  | `/api/requests` | Browse open requests (with `search`, `subject`, `urgency` filters) |
| GET  | `/api/requests?mine=1` | Get current user's requests |
| POST | `/api/requests` | Create a request |
| GET  | `/api/requests/:id` | Get a single request |
| DELETE | `/api/requests/:id` | Delete a request |
| PATCH | `/api/requests/:id` | Update request status |
| POST | `/api/requests/:id/offers` | Submit an offer (always sends offer message to conversation) |
| GET  | `/api/requests/:id/offers` | Get offers for a request |
| POST | `/api/offers/:id/accept` | Accept an offer (creates session + sends acceptance message) |
| GET  | `/api/conversations` | Get all conversations |
| POST | `/api/conversations` | Start a conversation |
| GET  | `/api/conversations/:id/messages` | Get messages |
| POST | `/api/conversations/:id/messages` | Send a message |
| GET  | `/api/sessions` | Get sessions (includes `conversation_id` for each) |
| PATCH | `/api/sessions/:id` | Update session status (sends thank-you + notifies requester to rate on complete) |
| POST | `/api/sessions/:id/rate` | Rate a helper (1–5 stars) |
| GET  | `/api/notifications` | Get notifications |
| POST | `/api/notifications/read-all` | Mark all notifications read |
| POST | `/api/notifications/:id/read` | Mark one notification read |
| PATCH | `/api/users/me` | Update profile |
| GET  | `/api/stats` | Get dashboard stats |
