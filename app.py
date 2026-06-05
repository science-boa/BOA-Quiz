st.title("Quiz Workspace")

# Create a left column (wide) and a right column (wide)
col1, col2 = st.columns([2, 3]) 

with col1:
    student_email = st.text_input("Email Address:")
    st.video(quiz_data["video_url"])
    st.caption("Tip: You can watch the video while answering questions on the right.")

with col2:
    # Put questions inside a sub-container or scrollable block
    with st.container(height=500): # Height bounding turns it into a scroll pane
        for mc in quiz_data["multiple_choice"]:
            st.radio(mc["text"], [mc["A"], mc["B"], mc["C"], mc["D"]])

        st.text_area(quiz_data["long_answer"]["text"])
        st.form_submit_button("Submit")
