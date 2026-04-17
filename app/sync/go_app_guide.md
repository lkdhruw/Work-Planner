# Go (Gin + GORM) Integration Guide — Work Planner Sync

This document explains how to create a **Go backend** using the **Gin Web Framework** and **GORM** to expose a REST API that the Work Planner desktop client can sync with.

---

## 1. Prerequisites

Initialize a new Go module and install the dependencies:

```bash
mkdir workplanner-api && cd workplanner-api
go mod init workplanner
go get -u github.com/gin-gonic/gin
go get -u gorm.io/gorm
go get -u gorm.io/driver/sqlite # or postgres / mysql
```

---

## 2. Models (GORM)

Create a `models/models.go` file to define your database schemas.

```go
package models

import (
	"time"
	"gorm.io/gorm"
)

type User struct {
	ID       uint   `gorm:"primaryKey"`
	Username string `gorm:"uniqueIndex"`
	Token    string `gorm:"uniqueIndex"`
}

type Profile struct {
	ID        uint      `gorm:"primaryKey" json:"id"`
	UserID    uint      `json:"-"`
	Name      string    `json:"name"`
	Color     string    `gorm:"default:'#7C3AED'" json:"color"`
	CreatedAt time.Time `json:"created_at"`
}

type Task struct {
	ID                 uint      `gorm:"primaryKey" json:"id"`
	UserID             uint      `json:"-"`
	ProfileID          *uint     `json:"profile"`
	Title              string    `json:"title"`
	Description        string    `json:"description"`
	DueDate            *string   `json:"due_date"`
	IsCompleted        bool      `gorm:"default:false" json:"is_completed"`
	ReminderType       string    `gorm:"default:'none'" json:"reminder_type"`
	ReminderTime       *string   `json:"reminder_time"`
	ReminderDatetime   *time.Time `json:"reminder_datetime"`
	ReminderDays       *string   `json:"reminder_days"` // Store as JSON string "[1,2]"
	ReminderDayOfMonth *int      `json:"reminder_day_of_month"`
	CreatedAt          time.Time `json:"created_at"`
	UpdatedAt          time.Time `json:"updated_at"`

	Subtasks []SubTask `gorm:"foreignKey:TaskID;constraint:OnDelete:CASCADE;" json:"subtasks"`
}

type SubTask struct {
	ID          uint      `gorm:"primaryKey" json:"id"`
	TaskID      uint      `json:"task_id"`
	Title       string    `json:"title"`
	IsCompleted bool      `gorm:"default:false" json:"is_completed"`
	CreatedAt   time.Time `json:"created_at"`
}
```

---

## 3. Middleware (Auth)

Create an authentication middleware to validate the `Authorization: Token <token>` header supplied by the desktop client.

```go
// middleware/auth.go
package middleware

import (
	"net/http"
	"strings"
	"workplanner/models"

	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
)

func TokenAuthMiddleware(db *gorm.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		authHeader := c.GetHeader("Authorization")
		if authHeader == "" || !strings.HasPrefix(authHeader, "Token ") {
			c.JSON(http.StatusUnauthorized, gin.H{"error": "Missing or invalid token"})
			c.Abort()
			return
		}

		tokenStr := strings.TrimPrefix(authHeader, "Token ")

		var user models.User
		if err := db.Where("token = ?", tokenStr).First(&user).Error; err != nil {
			c.JSON(http.StatusUnauthorized, gin.H{"error": "Invalid token"})
			c.Abort()
			return
		}

		// Store user in context
		c.Set("user", &user)
		c.Next()
	}
}
```

---

## 4. Main App & Routing

Set up `main.go`.

```go
// main.go
package main

import (
	"net/http"
	"strings"

	"workplanner/middleware"
	"workplanner/models"

	"github.com/gin-gonic/gin"
	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

func main() {
	db, err := gorm.Open(sqlite.Open("workplanner.db"), &gorm.Config{})
	if err != nil {
		panic("failed to connect database")
	}

	// Migrate the schema
	db.AutoMigrate(&models.User{}, &models.Profile{}, &models.Task{}, &models.SubTask{})

	r := gin.Default()

	// -- Desktop Auth Flow --
	r.GET("/api/desktop-auth/", func(c *gin.Context) {
		nextUrl := c.Query("next")

		// TODO: Implement actual HTML authentication here.
		// For now, we mock the fact that the user authenticated successfully.
		token := "mock_token_123"

		if nextUrl != "" {
			separator := "?"
			if strings.Contains(nextUrl, "?") {
				separator = "&"
			}
			c.Redirect(http.StatusFound, nextUrl+separator+"token="+token)
			return
		}

		c.JSON(http.StatusOK, gin.H{"token": token})
	})

	// Protected API Routes
	api := r.Group("/api")
	api.Use(middleware.TokenAuthMiddleware(db))
	{
		api.GET("/ping/", func(c *gin.Context) {
			user, _ := c.Get("user")
			c.JSON(http.StatusOK, gin.H{"status": "ok", "user": user.(*models.User).Username})
		})

		// -- Profiles --
		api.GET("/profiles/", func(c *gin.Context) {
			user, _ := c.Get("user")
			var profiles []models.Profile
			db.Where("user_id = ?", user.(*models.User).ID).Find(&profiles)
			c.JSON(http.StatusOK, profiles)
		})

		api.POST("/profiles/", func(c *gin.Context) {
			user, _ := c.Get("user")
			var profile models.Profile
			if err := c.ShouldBindJSON(&profile); err != nil {
				c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
				return
			}
			profile.UserID = user.(*models.User).ID
			db.Create(&profile)
			c.JSON(http.StatusOK, profile)
		})

		// -- Tasks --
		api.GET("/tasks/", func(c *gin.Context) {
			user, _ := c.Get("user")
			profileID := c.Query("profile")
			
			query := db.Preload("Subtasks").Where("user_id = ?", user.(*models.User).ID)
			if profileID != "" {
				query = query.Where("profile_id = ?", profileID)
			}

			var tasks []models.Task
			query.Find(&tasks)
			c.JSON(http.StatusOK, tasks)
		})

		api.POST("/tasks/", func(c *gin.Context) {
			user, _ := c.Get("user")
			var task models.Task
			if err := c.ShouldBindJSON(&task); err != nil {
				c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
				return
			}
			task.UserID = user.(*models.User).ID
			db.Create(&task)
			c.JSON(http.StatusOK, task)
		})

		// TODO: Add PATCH and DELETE for profiles, tasks, and subtasks endpoints
	}

	r.Run(":8080")
}
```

---

## 5. Desktop Auth Flow Summary

```
Desktop App                         Browser                      Go/Gin Server
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
