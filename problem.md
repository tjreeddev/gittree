\# Problem



I want a better way to visualize what is happening inside a Git repository while I am working on a project. Git commands can show branches, commits, merges, and history, but I want to see that information as an interactive visual tree in the terminal. I want the tree to update while I perform Git commands so I can more easily understand how the project's branches and history are changing.



\# Initial requirements



\- R1. The program can open and read a local Git repository.



\- R2. The program displays the repository's commits as a visual tree in the terminal.



\- R3. Different branches are displayed as distinguishable lanes in the tree.



\- R4. The tree shows relationships between commits, including branches splitting and merging.



\- R5. The user can navigate through and select branches and commits using the keyboard.



\- R6. Selecting a branch or commit displays information about it, such as the branch name, commit hash, and commit message.



\- R7. The program automatically refreshes when the Git repository changes while the program is running.



\- R8. New commits or branches are visually highlighted when they appear so changes are easy to notice.



\- R9. The program is read-only and does not commit, merge, switch branches, stage files, delete branches, or otherwise modify the repository.



\- R10. The program runs on the user's own computer with one command.

