# NodeJS (Express + Prisma) Integration Guide — Work Planner Sync

This document explains how to create a **NodeJS/Express backend** using **Prisma ORM** to expose a REST API that the Work Planner desktop client can sync with. 

---

## 1. Prerequisites

Initialize your Node.js project and install required dependencies:

```bash
mkdir workplanner-api && cd workplanner-api
npm init -y
npm install express cors body-parser
npm install prisma --save-dev
npm install @prisma/client
npx prisma init
```

---

## 2. Models (Prisma Schema)

Modify your `prisma/schema.prisma` file:

```prisma
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "sqlite" // or "postgresql", "mysql"
  url      = env("DATABASE_URL")
}

model User {
  id       Int       @id @default(autoincrement())
  username String    @unique
  token    String    @unique
  profiles Profile[]
  tasks    Task[]
}

model Profile {
  id      Int    @id @default(autoincrement())
  name    String
  color   String @default("#7C3AED")
  userId  Int
  user    User   @relation(fields: [userId], references: [id])
  tasks   Task[]
}

model Task {
  id                  Int       @id @default(autoincrement())
  title               String
  description         String    @default("")
  dueDate             DateTime?
  isCompleted         Boolean   @default(false)
  reminderType        String    @default("none")
  reminderTime        String?
  reminderDatetime    DateTime?
  reminderDays        String?   // Store as JSON string, e.g. "[1, 3]"
  reminderDayOfMonth  Int?
  
  userId              Int
  user                User      @relation(fields: [userId], references: [id])
  
  profileId           Int?
  profile             Profile?  @relation(fields: [profileId], references: [id])
  
  subtasks            SubTask[]
}

model SubTask {
  id          Int     @id @default(autoincrement())
  title       String
  isCompleted Boolean @default(false)
  
  taskId      Int
  task        Task    @relation(fields: [taskId], references: [id], onDelete: Cascade)
}
```

Run migrations:
```bash
npx prisma migrate dev --name init
```

---

## 3. Express App & Middleware

Create `index.js` to set up your Express server and authorization middleware.

```javascript
const express = require('express');
const cors = require('cors');
const { PrismaClient } = require('@prisma/client');

const prisma = new PrismaClient();
const app = express();

app.use(cors());
app.use(express.json());

// Token Authentication Middleware
const authenticateToken = async (req, res, next) => {
  const authHeader = req.headers['authorization'];
  if (!authHeader || !authHeader.startsWith('Token ')) {
    return res.status(401).json({ error: 'Missing or invalid token' });
  }

  const token = authHeader.split(' ')[1];
  const user = await prisma.user.findUnique({ where: { token } });

  if (!user) return res.status(401).json({ error: 'Invalid token' });

  req.user = user;
  next();
};
```

---

## 4. API Endpoints

Add the required syncing routes to your `index.js` file:

```javascript
// -- Ping --
app.get('/api/ping/', authenticateToken, (req, res) => {
  res.json({ status: 'ok', user: req.user.username });
});

// -- Desktop Auth Flow --
app.get('/api/desktop-auth/', async (req, res) => {
  const nextUrl = req.query.next || '';
  
  // NOTE: Implement your actual login UI here. 
  // We're mimicking an established authenticated session:
  const token = "mock_token_123"; 

  if (nextUrl) {
    const separator = nextUrl.includes('?') ? '&' : '?';
    return res.redirect(`${nextUrl}${separator}token=${token}`);
  }
  
  res.json({ token });
});

// -- Profiles --
app.get('/api/profiles/', authenticateToken, async (req, res) => {
  const profiles = await prisma.profile.findMany({
    where: { userId: req.user.id }
  });
  res.json(profiles);
});

app.post('/api/profiles/', authenticateToken, async (req, res) => {
  const { name, color } = req.body;
  const profile = await prisma.profile.create({
    data: { name, color, userId: req.user.id }
  });
  res.json(profile);
});

// -- Tasks --
app.get('/api/tasks/', authenticateToken, async (req, res) => {
  const { profile } = req.query;
  const tasks = await prisma.task.findMany({
    where: { 
      userId: req.user.id,
      ...(profile ? { profileId: parseInt(profile) } : {})
    },
    include: { subtasks: true }
  });
  
  // Map Prisma properties to DRF naming conventions if needed
  const mappedTasks = tasks.map(t => ({
    ...t,
    due_date: t.dueDate,
    is_completed: t.isCompleted,
    reminder_type: t.reminderType,
    profile: t.profileId
  }));
  
  res.json(mappedTasks);
});

app.post('/api/tasks/', authenticateToken, async (req, res) => {
  const { title, description, profile: profileId, due_date, is_completed } = req.body;
  const task = await prisma.task.create({
    data: {
      userId: req.user.id,
      profileId,
      title,
      description,
      dueDate: due_date ? new Date(due_date) : null,
      isCompleted: is_completed
    }
  });
  
  res.json({ ...task, profile: task.profileId });
});

// Start the server
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Server running on http://localhost:${PORT}`);
});
```

---

## 5. Desktop Auth Flow Summary

```
Desktop App                         Browser                      NodeJS Server
    |                                  |                              |
    |── opens login URL ──────────────>|                              |
    |   /api/desktop-auth/?next=...    |── GET /api/desktop-auth/ ──>|
    |                                  |── Server renders Login UI ──|
    |                                  |── POST credentials ─────────>|
    |                                  |── Server generates Token     |
    |                                  |<── redirect to localhost ───|
    |                                  |   http://localhost:9731/auth/callback?token=XXX
    |<── local server captures token ──|                              |
    |   stores token in settings DB    |                              |
    |── subsequent API calls with ────────────────────────────────────>|
    |   Authorization: Token XXX                                      |
```

---

## 6. API Endpoint Reference

| Method   | URL                                      | Description                         |
|----------|------------------------------------------|-------------------------------------|
| GET      | /api/ping/                               | Health check (requires token)       |
| GET      | /api/desktop-auth/                       | Browser-based sign-in trigger       |
| GET      | /api/profiles/                           | List user's profiles                |
| POST     | /api/profiles/                           | Create profile                      |
| PATCH    | /api/profiles/:id/                       | Update profile                      |
| DELETE   | /api/profiles/:id/                       | Delete profile                      |
| GET      | /api/tasks/                              | List tasks (filter: ?profile=id)    |
| POST     | /api/tasks/                              | Create task                         |
| PATCH    | /api/tasks/:id/                          | Update task                         |
| DELETE   | /api/tasks/:id/                          | Delete task                         |
| GET      | /api/tasks/:task_id/subtasks/            | List subtasks for a task            |
| POST     | /api/tasks/:task_id/subtasks/            | Add subtask                         |
| PATCH    | /api/tasks/:task_id/subtasks/:sub_id/    | Update subtask                      |
| DELETE   | /api/tasks/:task_id/subtasks/:sub_id/    | Delete subtask                      |
