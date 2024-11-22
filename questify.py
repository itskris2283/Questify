import tkinter as tk
from tkinter import messagebox,ttk
import requests
import random
import html
import csv
import os
import json
from cryptography.fernet import Fernet
import matplotlib.pyplot as plt
import pygame
import smtplib
import re

def startapp():
    pygame.mixer.init()
    correct_sound = pygame.mixer.Sound("correct.mp3")
    wrong_sound = pygame.mixer.Sound("wrong.mp3")
    score = 0
    current_question = 0
    quiz_data = []
    answer_buttons = []
    user_answers = []
    leaderboard_file = "leaderboard.csv"
    user_data_file = "users.json"
    key_file = "secret.key"

    def plot_user_progress():
        username = username_entry.get()
        users = load_user_data()

        if username in users:
            scores = users[username].get('score_history', [])
            categories = users[username].get('category_history', [])
            print(categories)

            if not scores:
                messagebox.showinfo("No Data", "No valid scores found for this user.")
                return

            plt.figure(figsize=(10, 5))
            plt.plot(scores, marker='o')
            plt.title(f"Score Progress for {username}")
            plt.xlabel("Quiz Attempts")
            plt.ylabel("Score")

            # Create x-tick labels with attempt number and category name
            x_labels = [f"Attempt {i + 1}\n({categories[i] if i < len(categories) else 'Unknown'})" 
                        for i in range(len(scores))]
            plt.xticks(range(len(scores)), x_labels, rotation=25)  # Rotate x-tick labels

            plt.yticks(range(0, max(scores) + 1))
            plt.grid()

            plt.subplots_adjust(bottom=0.30)
            plt.show()
        else:
            messagebox.showinfo("No Data", "No score history found for this user.")


    def load_key():
        if os.path.exists(key_file):
            with open(key_file, 'rb') as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(key_file, 'wb') as f:
                f.write(key)
            return key

    key = load_key()
    cipher = Fernet(key)

    def save_score(username, score, category):
        users = load_user_data()
        if username in users:
            if 'score_history' not in users[username]:
                users[username]['score_history'] = []
            if 'category_history' not in users[username]:
                users[username]['category_history'] = []

            users[username]['score_history'].append(score)  # Save the score
            users[username]['category_history'].append(category)  # Save the category

        save_user_data(users)

    def load_leaderboard_data():
        leaderboard = {}
        if os.path.exists(leaderboard_file):
            with open(leaderboard_file, 'r') as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) == 3:  # Expecting username, score, and category
                        try:
                            leaderboard[row[0]] = {'score': int(row[1]), 'category': row[2]}  # Store as a dictionary
                        except ValueError:
                            print(f"Skipping invalid score for {row[0]}: {row[1]}")
        return leaderboard

    def show_leaderboard():
        leaderboard = load_leaderboard_data()
        leaderboard_window = tk.Toplevel(root)
        leaderboard_window.title("Leaderboard")
        leaderboard_window.geometry("960x300")

        tk.Label(leaderboard_window, text="Leaderboard", font=("Arial", 16)).pack(pady=10)

        # Create a style
        style = ttk.Style()
        style.configure("Treeview", font=("Arial", 12))  # Set the font for the Treeview items
        style.configure("Treeview.Heading", font=("Arial", 14, 'bold'))  # Set the font for the headings

        # Create a frame to contain the Treeview and scrollbar
        frame = tk.Frame(leaderboard_window)
        frame.pack(fill='both', expand=True)

        # Create Treeview
        tree = ttk.Treeview(frame, columns=('Username', 'Score', 'Category'), show='headings')
        tree.heading('Username', text='Username')
        tree.heading('Score', text='Score')
        tree.heading('Category', text='Category')

        # Center-align the columns
        tree.column('Username', anchor='center', width=150)
        tree.column('Score', anchor='center', width=100)
        tree.column('Category', anchor='center', width=150)

        # Pack the Treeview to fill the left side
        tree.pack(side='left', fill='both', expand=True)

        # Add scrollbar and pack it to the right
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side='right', fill='y')

        sorted_leaderboard = sorted(leaderboard.items(), key=lambda x: x[1]['score'], reverse=True)
        print(sorted_leaderboard)

        # Insert data into Treeview
        for username, data in sorted_leaderboard:
            tree.insert('', 'end', values=(username, data['score'], data['category']))

        if not sorted_leaderboard:
            tree.insert('', 'end', values=("No scores yet.", "", ""))

    def on_quiz_completed():
        global score
        score_label.config(text="")
        username = username_entry.get()
        selected_category = category_var.get()  # Get the selected category
        save_score(username, score, selected_category)
        update_leaderboard(username, score, selected_category)  # Pass the category here

        # Clear the quiz frame and show completion message
        for widget in frame_quiz.winfo_children():
            widget.pack_forget()  # Hide all widgets in the quiz frame

        completion_label = tk.Label(frame_quiz, text="Quiz Completed!", font=("Arial", 20))
        completion_label.pack(pady=20)

        final_score_label = tk.Label(frame_quiz, text=f"Your final score: {score}", font=("Arial", 16))
        final_score_label.pack(pady=10)

        # Disable or remove buttons and images
        next_button.place_forget()  # Hide the Next button
        previous_button.place_forget()  # Hide the Previous button
        submit_button.config(state="disabled")  # Disable the Submit button
        for button in answer_buttons:
            button.config(state="disabled")  # Disable all answer buttons

        # Optionally, you can add a prompt to restart the quiz here
        if messagebox.askyesno("Restart Quiz", "Do you want to restart the quiz?"):
            reset_quiz()  # Reset the quiz state
            frame_quiz.pack_forget()  # Hide the quiz frame
            frame_category.pack(fill="both", expand=True)  # Show category selection frame

    def fetch_categories():
        try:
            response = requests.get("https://opentdb.com/api_category.php")
            response.raise_for_status()
            return response.json()['trivia_categories']
        except requests.RequestException as e:
            messagebox.showerror("Error", f"Could not fetch categories: {e}")
            return []

    difficulty_levels = ["easy", "medium", "hard"]

    def fetch_quiz_data(category_id, question_count=10, difficulty='easy'):
        global quiz_data, current_question, user_answers
        try:
            response = requests.get(f"https://opentdb.com/api.php?amount={question_count}&category={category_id}&difficulty={difficulty}")
            response.raise_for_status()
            quiz_data = response.json().get('results', [])

            if not quiz_data:
                messagebox.showerror("Error", "No quiz data returned. Please try again.")
                return

            current_question = 0
            user_answers = [None] * len(quiz_data)
            load_question()
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error", f"An error occurred while fetching quiz data: {e}")

    def load_question():
        global current_question, quiz_data, user_answers

        if current_question < len(quiz_data):
            question_data = quiz_data[current_question]
            question = html.unescape(question_data['question'])
            correct_answer = html.unescape(question_data['correct_answer'])
            incorrect_answers = [html.unescape(answer) for answer in question_data['incorrect_answers']]

            all_answers = incorrect_answers + [correct_answer]
            random.shuffle(all_answers)

            question_label.config(text=question)
            var.set(user_answers[current_question] if user_answers[current_question] is not None else None)

            for i, answer in enumerate(all_answers):
                answer_buttons[i].config(text=answer, value=answer)

            # Check the user's previous answer if exists
            if user_answers[current_question] is not None:
                if user_answers[current_question] == correct_answer:
                    result_label.config(text="You got it right!", fg="green")
                else:
                    result_label.config(text=f"Your answer: {user_answers[current_question]} | Correct answer: {correct_answer}", fg="red")
                for button in answer_buttons:
                    button.config(state="disabled")
                submit_button.config(state="disabled")
            else:
                result_label.config(text="")
                for button in answer_buttons:
                    button.config(state="normal")
                submit_button.config(state="normal")

            # Handle previous button state
            previous_button.config(state="normal" if current_question > 0 else "disabled")

            # Change Next button text for the last question
            if current_question == len(quiz_data) - 1:
                next_button.config(image=finimage, command=on_quiz_completed)  # Change text and command
            else:
                next_button.config(image=nxtimage, command=next_question)  # Reset to default for other questions
        else:
            # This shouldn't happen; however, in case it does, complete the quiz
            question_label.config(text="Quiz Completed!")
            on_quiz_completed()

    def check_answer():
        global current_question, score,quiz_data,user_answers,selected_answer
        if not quiz_data or current_question >= len(quiz_data):
            messagebox.showerror("Error", "No quiz data found!")
            return

        selected_answer = var.get()
        if not selected_answer:
            messagebox.showwarning("No Answer", "Please select an answer before submitting!")
            return

        question_data = quiz_data[current_question]
        correct_answer = html.unescape(question_data['correct_answer'])

        if selected_answer == correct_answer:
            result_label.config(text="Correct!", fg="green")
            score += 1
            correct_sound.play()
        else:
            result_label.config(text=f"Wrong! The correct answer was: {correct_answer}", fg="red")
            wrong_sound.play()

        score_label.config(text=f"Score: {score}")
        user_answers[current_question] = selected_answer

        for button in answer_buttons:
            button.config(state="disabled")
        submit_button.config(state="disabled")

    def next_question():
        global current_question
        current_question += 1
        load_question()

    def previous_question():
        global current_question
        if current_question > 0:
            current_question -= 1
            load_question()

    def update_leaderboard(username, score, category):
        leaderboard = load_leaderboard_data()
        if username in leaderboard:
            leaderboard[username]['score'] = max(leaderboard[username]['score'], score)  # Keep the highest score
        else:
            leaderboard[username] = {'score': score, 'category': category}  # Store category with score
        
        with open(leaderboard_file, 'w', newline='') as f:
            writer = csv.writer(f)
            for user, data in leaderboard.items():
                writer.writerow([user, data['score'], data['category']])

    def reset_quiz():
        global score, current_question, quiz_data, user_answers
        score = 0
        current_question = 0
        quiz_data = []
        user_answers = []
        score_label.config(text="Score: 0")
        result_label.config(text="")

        for widget in frame_quiz.winfo_children():
            widget.pack_forget()  # Hide all widgets in the quiz frame

        question_label.pack(pady=20)

        for button in answer_buttons:
            button.pack(anchor='w')

        submit_button.pack(pady=10)
        next_button.place(x=650, y=300)
        previous_button.place(x=50, y=300)

        # Reset the state of next and previous buttons
        next_button.config(state="normal")
        previous_button.config(state="disabled")

        # Reset result label
        result_label.pack(pady=10)
        score_label.place(x=300,y=400)
        
    def start_quiz():
        selected_category = category_var.get()
        question_count = question_count_entry.get()
        selected_difficulty = difficulty_var.get()

        if selected_category == "Select a category" or not question_count.isdigit() or not (1 <= int(question_count) <= 50):
            result_label.config(text="Please select a category and enter a valid number of questions (1-50)!", fg="red")
            return

        category_id = selected_category.split("(")[-1].strip(")")
        fetch_quiz_data(category_id, int(question_count), selected_difficulty)

        frame_category.pack_forget()
        frame_quiz.pack(fill="both", expand=True)

        # Load the first question after the quiz starts
        load_question()

    def on_exit():
        if messagebox.askokcancel("Quit", "Do you really want to quit?"):
            root.destroy()

    def login():
        username = username_entry.get()
        password = password_entry.get()

        users = load_user_data()
        if username in users:
            try:
                encrypted_password = users[username]['password']
                decrypted_password = cipher.decrypt(encrypted_password.encode()).decode()

                if decrypted_password == password:
                    reset_quiz()
                    frame_login.pack_forget()
                    frame_category.pack(fill="both", expand=True)
                
                else:
                    messagebox.showerror("Login Failed", "Invalid username or password.")
            except Exception as e:
                messagebox.showerror("Decryption Error", f"An error occurred during login: {e}")
        else:
            messagebox.showerror("Login Failed", "Invalid username or password.")

    def is_valid_email(email):
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(email_regex, email) is not None

    def signup():
        username = signup_username_entry.get()
        password = signup_password_entry.get()
        email = signup_email_entry.get()  # Get the email entered by the user

        users = load_user_data()
        if username in users:
            messagebox.showerror("Sign Up Failed", "Username already exists.")
        else:
            try:
                if not is_valid_email(email):
                    messagebox.showerror("Invalid Email", "Please enter a valid email address.")
                    return

                if password.lower() == "password":
                    messagebox.showerror("Invalid Password", "Password cannot be 'password'. Please choose a different password.")
                    return

                if isinstance(password, str) and password:
                    encrypted_password = cipher.encrypt(password.encode()).decode()
                    # Store the email along with the username and password
                    users[username] = {
                        "password": encrypted_password,
                        "email": email,  # Save the email
                        "score_history": []
                    }
                    save_user_data(users)

                    # Send OTP to the user's email
                    otp = send_otp_to_email(email,2)
                    if otp:
                        # Prompt the user to enter the OTP
                        otp_window = tk.Toplevel(root)
                        otp_window.title("Enter OTP")
                        otp_window.geometry("300x200")

                        tk.Label(otp_window, text="Enter the 4-digit OTP sent to your email:").pack(pady=10)
                        otp_entry = tk.Entry(otp_window)
                        otp_entry.pack(pady=10)

                        def verify_otp():
                            entered_otp = otp_entry.get()
                            if entered_otp == otp:
                                messagebox.showinfo("Sign Up Success", "Account created successfully! You can now log in.")
                                otp_window.destroy()
                                frame_signup.pack_forget()
                                frame_login.pack(fill="both", expand=True)
                            else:
                                messagebox.showerror("Invalid OTP", "The OTP you entered is incorrect. Please try again.")

                        tk.Button(otp_window, text="Verify OTP", command=verify_otp).pack(pady=20)
                    else:
                        messagebox.showerror("Error", "Failed to send OTP. Please try again.")
            except Exception as e:
                messagebox.showerror("Encryption Error", f"An error occurred during sign-up: {e}")

    def load_user_data():
        if os.path.exists(user_data_file):
            with open(user_data_file, 'r') as f:
                content = f.read()
                if content:
                    try:
                        return json.loads(content)
                    except json.JSONDecodeError:
                        print("Error: JSON data is corrupted. Returning empty user data.")
                        return {}
                else:
                    print("Warning: User data file is empty. Returning empty user data.")
                    return {}
        return {}

    def save_user_data(users):
        with open(user_data_file, 'w') as f:
            json.dump(users, f, indent=4)

    def send_otp_to_email(email,n):
        # Generate a random 4-digit OTP
        otp = str(random.randint(1000, 9999))

        # Email configuration
        sender_email = "krishsingh.genaibu@gmail.com"
        sender_password = "typb food zdfy dlic"
        smtp_server = "smtp.gmail.com"
        smtp_port = 587

        # Create the email message
        if n==1:
            subject = "Password Recovery OTP"
            body = f"Your OTP for password recovery is: {otp}"
        elif n==2:
            subject = "Signup OTP"
            body = f"Your OTP for Signup is: {otp}"            

        message = f"Subject: {subject}\n\n{body}"

        try:
            # Connect to Gmail SMTP server and send the email
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()  # Secure the connection
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, email, message)
                print(f"OTP sent to {email}")
                return otp  # Return the OTP for verification
        except Exception as e:
            print(f"Error: {e}")
            return None

    def forgot_password():
        def retrieve_password():
            username = username_entry.get()
            users = load_user_data()

            if username in users:
                email = users[username]["email"]  # Retrieve email from user data
                otp = send_otp_to_email(email,1)  # Send OTP to the user's email

                if otp:  # If OTP was successfully sent
                    # Prompt the user to enter the OTP
                    otp_window = tk.Toplevel(root)
                    otp_window.title("Enter OTP")
                    otp_window.geometry("300x200")

                    tk.Label(otp_window, text="Enter the 4-digit OTP sent to your email:").pack(pady=10)
                    otp_entry = tk.Entry(otp_window)
                    otp_entry.pack(pady=10)

                    def verify_otp():
                        entered_otp = otp_entry.get()
                        if entered_otp == otp:
                            # OTP matches, show password
                            encrypted_password = users[username]['password']
                            decrypted_password = cipher.decrypt(encrypted_password.encode()).decode()
                            messagebox.showinfo("Your Password", f"Password for '{username}': {decrypted_password}")
                            otp_window.destroy()
                        else:
                            messagebox.showerror("Invalid OTP", "The OTP you entered is incorrect. Please try again.")

                    tk.Button(otp_window, text="Verify OTP", command=verify_otp).pack(pady=20)
                else:
                    messagebox.showerror("Error", "Failed to send OTP. Please try again.")
            else:
                messagebox.showerror("Error", "Username not found.")

        # Create the password retrieval window
        password_window = tk.Toplevel(root)
        password_window.title("Forgot Password")
        password_window.geometry("300x200+300+100")
        password_window.resizable(False,False)

        tk.Label(password_window, text="Enter your username:").pack(pady=10)

        username_entry = tk.Entry(password_window)
        username_entry.pack(pady=10)

        tk.Button(password_window, text="Send OTP", command=retrieve_password).pack(pady=20)
        tk.Button(password_window, text="Close", command=password_window.destroy).pack(pady=5)

    def logout():
        reset_quiz()
        frame_category.pack_forget()
        frame_quiz.pack_forget()
        frame_signup.pack_forget()
        frame_login.pack(fill="both", expand=True)

    def create_menu():
        menu = tk.Menu(root)
        root.config(menu=menu)
        file_menu = tk.Menu(menu)
        menu.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Show Leaderboard", command=show_leaderboard)
        file_menu.add_command(label="Show Progress", command=plot_user_progress)
        file_menu.add_separator()
        file_menu.add_command(label="Logout", command=logout)
        file_menu.add_command(label="Exit", command=on_exit)

    # Create main Tkinter window
    root = tk.Tk()
    root.title("Quiz Application")
    root.geometry("925x500+300+100")
    root.resizable(False, False)
    root.title("Questify")

    #Import neccessary images
    logo=tk.PhotoImage(file="quizapplogo.png")
    nxtimage=tk.PhotoImage(file="Next Question.png")
    subimage=tk.PhotoImage(file="Submit.png")
    previmage=tk.PhotoImage(file="Previous Question.png")
    finimage=tk.PhotoImage(file="Finish Quiz.png")
    loginimage=tk.PhotoImage(file="login.png")
    signupimage=tk.PhotoImage(file="signup.png")
    startquiz=tk.PhotoImage(file="start quiz.png")
        
    # Create frames
    frame_login = tk.Frame(root,bg="#fff")
    frame_signup = tk.Frame(root,bg="#fff")
    frame_category = tk.Frame(root)
    frame_quiz = tk.Frame(root)
    
    root.iconphoto(False,logo)

    # Login Frame
    def on_enter_username(e,n):
        if n==1:
            if username_entry.get() == "Username":
                username_entry.delete(0, "end")
        elif n==2:
            if signup_username_entry.get() == "Username":
                signup_username_entry.delete(0, "end")

    def on_leave_username(e,n):
        if n==1:
            if username_entry.get() == "":
                username_entry.insert(0, "Username")
        elif n==2:
            if signup_username_entry.get() == "":
                signup_username_entry.insert(0,"Username")            

    tk.Label(frame_login,image=loginimage).place(x=50,y=50)
    tk.Label(frame_login,text="Sign in",fg="#57a1f8",bg="white",font="ariel 23 bold").place(x=600,y=5)
    tk.Frame(frame_login,width=295,height=2,bg="black").place(x=600,y=100)
    username_entry = tk.Entry(frame_login,width=25,border=0,bg="white",font="ariel 10 bold")
    username_entry.place(x=600,y=80)
    username_entry.insert(0,"Username")
    username_entry.bind("<FocusIn>",lambda e: on_enter_username(e,1))
    username_entry.bind("<FocusOut>",lambda e: on_leave_username(e,1))
    
    def on_enter_password(e,n):
        if n==1:
            if password_entry.get() == "Password":
                password_entry.delete(0, "end")
                password_entry.config(show="*")
        if n==2:
            if signup_password_entry.get() == "Password":
                signup_password_entry.delete(0, "end")
                signup_password_entry.config(show="*")

    def on_leave_password(e,n):
        if n==1:
            if password_entry.get() == "":
                password_entry.insert(0, "Password")
                password_entry.config(show="")  
        if n==2:
            if signup_password_entry.get() == "":
                signup_password_entry.insert(0, "Password")
                signup_password_entry.config(show="")

    def on_enter(e):
        if signup_email_entry.get()=="Email Address":
            signup_email_entry.delete(0,"end")
    def on_leave(e):
        if signup_email_entry.get() == "":
            signup_email_entry.insert(0, "Email Address")

    password_entry = tk.Entry(frame_login,width=20,border=0,bg="white",font="ariel 10 bold")
    password_entry.place(x=600,y=180)
    password_entry.insert(0,"Password")
    password_entry.bind("<FocusIn>",lambda e: on_enter_password(e,1))
    password_entry.bind("<FocusOut>",lambda e: on_leave_password(e,1))
    tk.Frame(frame_login,width=295,height=2,bg="black").place(x=600,y=200)

    tk.Button(frame_login,width=39,pady=7,border=0 ,text="Login",bg="#57a1f8",fg="white", command=login).place(x=600,y=250)
    tk.Button(frame_login, text="Sign Up",width=39,pady=7,border=0 ,command=lambda: [frame_login.pack_forget(), frame_signup.pack(fill="both", expand=True)]).place(x=600,y=300)
    tk.Button(frame_login, text="Forgot Password?",width=39,border=0, command=forgot_password).place(x=600,y=350)
    
    # Signup Frame
    tk.Label(frame_signup, image=signupimage).place(x=50,y=50)
    heading=tk.Label(frame_signup,text="Sign up",fg="#57a1f8",bg="white",font="Ariel 18 bold")
    heading.place(x=600,y=5)
    signup_username_entry = tk.Entry(frame_signup,width=25,border=0,fg="black",bg="white")
    signup_username_entry.place(x=600,y=80)
    signup_username_entry.insert(0,"Username")
    tk.Frame(frame_signup,width=300,height=2,bg="black").place(x=600,y=100)
    signup_username_entry.bind("<FocusIn>",lambda e: on_enter_username(e,2))
    signup_username_entry.bind("<FocusOut>",lambda e: on_leave_username(e,2))

    # tk.Label(frame_signup, text="Choose a Password").pack(pady=10)
    signup_password_entry = tk.Entry(frame_signup,width=20,border=0,bg="white",font="ariel 10 bold")
    signup_password_entry.place(x=600,y=160)
    signup_password_entry.insert(0,"Password")
    signup_password_entry.bind("<FocusIn>",lambda e: on_enter_password(e,2))
    signup_password_entry.bind("<FocusOut>",lambda e: on_leave_password(e,2))
    tk.Frame(frame_signup,width=300,height=2,bg="black").place(x=600,y=180)

    # tk.Label(frame_signup, text="Enter your Email").pack(pady=10)
    signup_email_entry = tk.Entry(frame_signup,width=20,border=0,bg="white",font="ariel 10 bold")
    signup_email_entry.place(x=600,y=250)
    signup_email_entry.insert(0,"Email Address")
    signup_email_entry.bind("<FocusIn>",on_enter)
    signup_email_entry.bind("<FocusOut>",on_leave)
    tk.Frame(frame_signup,width=300,height=2,bg="black").place(x=600,y=270)

    tk.Button(frame_signup, text="Sign Up", width=39,pady=7,border=0,command=signup).place(x=600,y=300)
    tk.Button(frame_signup, text="Back to Login", command=lambda: [frame_signup.pack_forget(), frame_login.pack(fill="both", expand=True)]).place(x=600,y=350)

    # Category Frame
    tk.Label(frame_category, text="Select Quiz Category", font=("Arial", 20)).place(x=50,y=20)
    category_var = tk.StringVar(value="Select a category")
    category_dropdown = tk.OptionMenu(frame_category,category_var,*["Select a category"] + [f"{cat['name']} ({cat['id']})" for cat in fetch_categories()])
    category_dropdown.configure(font="Ariel 16",border=1)
    category_dropdown.place(x=50,y=80)

    # Difficulty Level Selection
    tk.Label(frame_category, text="Select Difficulty Level", font=("Arial", 20)).place(x=600,y=20)
    difficulty_var = tk.StringVar(value="easy")  # Default to easy
    difficulty_dropdown = tk.OptionMenu(frame_category, difficulty_var, *difficulty_levels)
    difficulty_dropdown.configure(font="Ariel 16",border=1)
    difficulty_dropdown.place(x=700,y=80)

    tk.Label(frame_category, text="Number of Questions (1-50)", font=("Arial", 16)).place(x=300,y=200)
    question_count_entry = tk.Entry(frame_category)
    question_count_entry.place(x=350,y=240)
    tk.Button(frame_category, image=startquiz, command=start_quiz).place(x=300,y=270)

    # Quiz Frame
    question_label = tk.Label(frame_quiz, text="", font=("Arial", 18), wraplength=600)
    question_label.pack(pady=20)

    var = tk.StringVar()
    for _ in range(4):
        btn = tk.Radiobutton(frame_quiz, text="", font=("Ariel", 16),variable=var)
        btn.pack(anchor='w')
        answer_buttons.append(btn)

    submit_button = tk.Button(frame_quiz, image=subimage, command=check_answer)
    submit_button.pack(pady=10)

    next_button = tk.Button(frame_quiz, image=nxtimage, command=next_question,border=1)
    next_button.place(x=650,y=300)

    previous_button = tk.Button(frame_quiz, image=previmage, command=previous_question,border=1)
    previous_button.place(x=50,y=300)

    result_label = tk.Label(frame_quiz, text="")
    result_label.place(x=100,y=500)

    score_label = tk.Label(frame_quiz, text="Score: 0")
    score_label.place(x=100,y=450)

    frame_login.pack(fill="both", expand=True)
    create_menu()

    root.mainloop()

def loadingscreen():
    loading_window = tk.Tk()
    loading_window.geometry("600x400+300+200")
    loading_window.title("Loading...")
    loading_window.config(bg="#5ce1e6")
    lpage=tk.PhotoImage(file="loading page.png")
    label = tk.Label(loading_window,image=lpage, font=("Arial", 20))
    label.pack(pady=50)
    loading_window.overrideredirect(True)
    loading_window.after(3000, lambda: [loading_window.destroy(), startapp()])
    loading_window.mainloop()

loadingscreen()