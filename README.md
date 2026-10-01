# QLess

A virtual queue management platform that allows customers to join queues remotely, track their position in real time, and receive notifications while businesses manage branches, services, staff, bookings, and queues from one platform.

## Project Overview

QLess is designed to reduce physical waiting times and make queue management easier for both customers and businesses.

Customers can discover businesses, select a branch and service, join a virtual queue, track their position, receive estimated waiting times, and get notified when their turn approaches.

Business owners can manage their businesses, branches, services, operating hours, queues, staff, bookings, announcements, and queue analytics.

Admins manage the overall platform, including users, businesses, categories, reviews, suspicious activity, and audit logs.

---

## Key Features

### Customer

* Browse approved businesses without signing in
* Search and filter businesses
* View business branches, services, hours, and queue status
* Join virtual queues remotely
* Receive a queue number
* Track people ahead and current queue position
* View estimated waiting time
* Receive a recommended return time
* Receive real-time queue notifications
* Mark that they are on the way
* Check in when called
* Leave or cancel a queue
* View queue history
* Receive no-show warnings
* Make and manage service bookings
* Review businesses after completing a service
* Favorite businesses
* Receive business announcements

### Business Management

* Create and manage businesses
* Submit businesses for admin approval
* Manage multiple branches
* Manage branch addresses and contact information
* Add and manage services
* Configure operating hours
* Create and manage virtual queues
* Open, pause, resume, and close queues
* Set queue capacity
* Configure average service duration
* Configure no-show grace periods
* Manage branch staff
* Monitor customers waiting in queues
* Track customers who are on their way
* Manage bookings
* Publish announcements
* View reviews
* View queue analytics

### Staff

* Access assigned business and branch
* View branch services and operating hours
* Manage active queues
* View waiting customers
* See customers who are on their way
* Call the next customer
* Check in customers
* Mark customers as completed
* Mark customers as no-shows
* Pause and resume queues
* View queue history
* View branch bookings

### Admin

* View platform dashboard and statistics
* Manage user accounts
* Approve or reject businesses
* Activate or deactivate businesses and branches
* Manage categories
* Monitor queues
* Manage reviews
* Monitor suspicious activity
* View administrative audit logs

---

## User Roles

| Role               | Description                                                                           |
| ------------------ | ------------------------------------------------------------------------------------- |
| **Guest**          | Browse businesses and explore QLess without an account.                           |
| **Customer**       | Discover businesses, join virtual queues, manage bookings, and receive notifications. |
| **Business Owner** | Manage businesses, branches, services, queues, staff, bookings, and announcements.    |
| **Staff**          | Manage queues and customers at an assigned branch.                                    |
| **Admin**          | Manage and monitor the QLess platform, users, businesses, and activity.           |

---

## Tech Stack

### Backend

* Python
* FastAPI
* SQLAlchemy
* PostgreSQL
* Alembic
* JWT Authentication
* Pydantic

### Frontend

* React
* JavaScript
* HTML
* CSS

### Development Tools

* Git
* GitHub
* Postman
* Uvicorn

---

## Database Design (ERD)

![QLess Entity Relationship Diagram](plan/QLess-ERD.png)

---

## API Routes


# User Stories

## Guest

* As a guest, I can view the landing page explaining how QLess works.
* As a guest, I can browse approved businesses.
* As a guest, I can search for businesses by name or service.
* As a guest, I can filter businesses by category.
* As a guest, I can view a business's branches.
* As a guest, I can view the location of a branch.
* As a guest, I can see whether a branch is currently open.
* As a guest, I can view the services available at a branch.
* As a guest, I can view the queues available at a branch.
* As a guest, I can view the current queue status.
* As a guest, I can view business announcements.
* As a guest, I can sign up.
* As a guest, I can log in.

---

## Customer

* As a customer, I can log in and log out.
* As a customer, I can view my profile.
* As a customer, I can edit my profile.
* As a customer, I can delete my account.
* As a customer, I can search for businesses.
* As a customer, I can filter businesses by category.
* As a customer, I can view business details.
* As a customer, I can view all branches of a business.
* As a customer, I can select a branch.
* As a customer, I can view a branch's address and contact information.
* As a customer, I can view a branch's operating hours.
* As a customer, I can view services available at a branch.
* As a customer, I can view queues available at a branch.
* As a customer, I can view the current status of a queue.
* As a customer, I can join an open queue.
* As a customer, I receive a queue number when I join.
* As a customer, I can see how many people are ahead of me.
* As a customer, I can see my current queue position.
* As a customer, I can see my estimated waiting time.
* As a customer, I can see a recommended return time.
* As a customer, I can receive real-time queue updates.
* As a customer, I can receive notifications about my queue.
* As a customer, I can mark that I am on my way.
* As a customer, I can leave a queue.
* As a customer, I can check in after being called.
* As a customer, I can view my queue history.
* As a customer, I can see when I have been called.
* As a customer, I can receive a warning after a no-show.
* As a customer, I can see when my account is temporarily restricted.
* As a customer, I can make a booking for an available service.
* As a customer, I can view my bookings.
* As a customer, I can update a booking.
* As a customer, I can cancel a booking.
* As a customer, I can review a business after completing a service.
* As a customer, I can edit my review.
* As a customer, I can delete my review.
* As a customer, I can favorite businesses.
* As a customer, I can remove businesses from my favorites.
* As a customer, I can view business announcements.

---

## Business Owner

* As a business owner, I can create a business.
* As a business owner, I can submit my business for admin approval.
* As a business owner, I can view my business approval status.
* As a business owner, I can edit my business information.
* As a business owner, I can resubmit a rejected business.
* As a business owner, I can deactivate my business.
* As a business owner, I can select a business category.
* As a business owner, I can create multiple branches for my business.
* As a business owner, I can edit branch information.
* As a business owner, I can deactivate a branch.
* As a business owner, I can manage branch addresses and contact information.
* As a business owner, I can add services to a branch.
* As a business owner, I can edit services.
* As a business owner, I can deactivate services.
* As a business owner, I can configure operating hours for each branch.
* As a business owner, I can create queues for a branch.
* As a business owner, I can open a queue.
* As a business owner, I can pause a queue.
* As a business owner, I can resume a queue.
* As a business owner, I can close a queue.
* As a business owner, I can set queue capacity.
* As a business owner, I can set average service duration.
* As a business owner, I can configure the no-show grace period.
* As a business owner, I can add staff members to a branch.
* As a business owner, I can update staff information.
* As a business owner, I can deactivate staff members.
* As a business owner, I can view active queues.
* As a business owner, I can view customers waiting in queues.
* As a business owner, I can view which customers are on their way.
* As a business owner, I can view reviews.
* As a business owner, I can create announcements.
* As a business owner, I can edit announcements.
* As a business owner, I can deactivate announcements.
* As a business owner, I can view bookings for a branch.
* As a business owner, I can view queue analytics.

---

## Staff

* As a staff member, I can log in.
* As a staff member, I can view my assigned business.
* As a staff member, I can view my assigned branch.
* As a staff member, I can view branch operating hours.
* As a staff member, I can view services offered at my branch.
* As a staff member, I can view all queues belonging to my branch.
* As a staff member, I can view customers waiting in a queue.
* As a staff member, I can see which customers are on their way.
* As a staff member, I can call the next customer.
* As a staff member, I can check in a customer.
* As a staff member, I can mark a customer as completed.
* As a staff member, I can mark a customer as a no-show.
* As a staff member, I can pause a queue.
* As a staff member, I can resume a queue.
* As a staff member, I can view queue history.
* As a staff member, I can view bookings for my branch.

---

## Admin

* As an admin, I can access an admin dashboard.
* As an admin, I can view platform statistics.
* As an admin, I can view all users.
* As an admin, I can activate or deactivate user accounts.
* As an admin, I can view all businesses.
* As an admin, I can view pending business applications.
* As an admin, I can approve a business.
* As an admin, I can reject a business.
* As an admin, I can deactivate an approved business.
* As an admin, I can view all business branches.
* As an admin, I can activate or deactivate a business branch.
* As an admin, I can manage business categories.
* As an admin, I can view all queues.
* As an admin, I can view reviews.
* As an admin, I can remove inappropriate reviews.
* As an admin, I can view accounts flagged for suspicious activity.
* As an admin, I can review audit logs.
