document.addEventListener("DOMContentLoaded", () => {
    // Draggable functionality
    const draggables = document.querySelectorAll(".movable-user");
    const dropzones = document.querySelectorAll(".group-users, .user-group-container-wrapper");

    // Make elements draggable
    draggables.forEach(draggable => {
        draggable.setAttribute("draggable", "true");

        draggable.addEventListener("dragstart", (event) => {
            event.dataTransfer.setData("text/plain", event.target.id);
            setTimeout(() => event.target.classList.add("hidden"), 0);
        });

        draggable.addEventListener("dragend", (event) => {
            event.target.classList.remove("hidden");
        });
    });

    // Add event listeners for drop zones
    dropzones.forEach(dropzone => {
        dropzone.addEventListener("dragover", (event) => {
            event.preventDefault();
            const afterElement = getDragAfterElement(dropzone, event.clientY);
            const dragging = document.querySelector(".hidden");

            if (afterElement == null) {
                dropzone.appendChild(dragging);
            } else {
                dropzone.insertBefore(dragging, afterElement);
            }
        });

        dropzone.addEventListener("drop", (event) => {
            event.preventDefault();
            const id = event.dataTransfer.getData("text/plain");
            const draggedElement = document.getElementById(id);

            if (draggedElement) {
                const afterElement = getDragAfterElement(dropzone, event.clientY);
                if (afterElement == null) {
                    dropzone.appendChild(draggedElement);
                } else {
                    dropzone.insertBefore(draggedElement, afterElement);
                }
                sortUsers(dropzone);
            }
        });

        // Sort the users inside the dropzone on page load
        sortUsers(dropzone);
    });

    // Function to detect the closest user under the cursor
    function getDragAfterElement(container, y) {
        const draggableElements = [...container.querySelectorAll(".movable-user:not(.hidden)")];

        return draggableElements.reduce((closest, child) => {
            const box = child.getBoundingClientRect();
            const offset = y - box.top - box.height / 2;
            return offset < 0 && offset > closest.offset ? { offset, element: child } : closest;
        }, { offset: Number.NEGATIVE_INFINITY }).element;
    }

    // Function to sort users alphabetically
    function sortUsers(container) {
        let users = Array.from(container.children);
        users.sort((a, b) => a.textContent.trim().localeCompare(b.textContent.trim()));
        users.forEach(user => container.appendChild(user));
    }

    // Editable group name functionality
    document.querySelectorAll(".editable-group-name").forEach(groupName => {
        groupName.contentEditable = "true";

        groupName.addEventListener("blur", () => {
            const newGroupName = groupName.textContent.trim();
            console.log("New group name:", newGroupName);

            // Send the new group name to the server
            fetch("/update-group-name/", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": "{{ csrf_token }}"
                },
                body: JSON.stringify({
                    groupName: newGroupName,
                    groupId: groupName.closest(".group-container").dataset.groupId
                })
            })
            .then(response => response.json())
            .then(data => {
                console.log("Group name updated successfully:", data);
            })
            .catch(error => {
                console.error("Error updating group name:", error);
            });
        });
    });
});
document.addEventListener("DOMContentLoaded", () => {
    const draggables = document.querySelectorAll(".movable-group");
    const availableGroups = document.getElementById("available-groups");
    const assignedGroups = document.getElementById("assigned-groups");

    // Make elements draggable
    draggables.forEach(draggable => {
        draggable.setAttribute("draggable", "true");

        draggable.addEventListener("dragstart", (event) => {
            event.dataTransfer.setData("text/plain", event.target.id);
            setTimeout(() => event.target.classList.add("hidden"), 0);
        });

        draggable.addEventListener("dragend", (event) => {
            event.target.classList.remove("hidden");
        });
    });

    // Add event listeners for both available and assigned groups (dropzones)
    [availableGroups, assignedGroups].forEach(dropzone => {
        dropzone.addEventListener("dragover", (event) => {
            event.preventDefault();
            const afterElement = getDragAfterElement(dropzone, event.clientY);
            const dragging = document.querySelector(".hidden");

            if (afterElement == null) {
                dropzone.appendChild(dragging);
            } else {
                dropzone.insertBefore(dragging, afterElement);
            }
        });

        dropzone.addEventListener("drop", (event) => {
            event.preventDefault();
            const id = event.dataTransfer.getData("text/plain");
            const draggedElement = document.getElementById(id);

            if (draggedElement) {
                const afterElement = getDragAfterElement(dropzone, event.clientY);
                if (afterElement == null) {
                    dropzone.appendChild(draggedElement);
                } else {
                    dropzone.insertBefore(draggedElement, afterElement);
                }
                sortGroups(dropzone);
            }
        });

        // Sort groups alphabetically on page load
        sortGroups(dropzone);
    });

    // Function to detect the closest group under the cursor
    function getDragAfterElement(container, y) {
        const draggableElements = [...container.querySelectorAll(".movable-group:not(.hidden)")];

        return draggableElements.reduce((closest, child) => {
            const box = child.getBoundingClientRect();
            const offset = y - box.top - box.height / 2;
            return offset < 0 && offset > closest.offset ? { offset, element: child } : closest;
        }, { offset: Number.NEGATIVE_INFINITY }).element;
    }

    // Function to sort groups alphabetically
    function sortGroups(container) {
        let groups = Array.from(container.children);
        groups.sort((a, b) => a.textContent.trim().localeCompare(b.textContent.trim()));
        groups.forEach(group => container.appendChild(group));
    }
});
document.addEventListener("DOMContentLoaded", () => {
    const dropzones = document.querySelectorAll(".group-users, .user-group-container-wrapper");

    dropzones.forEach(dropzone => {
        dropzone.addEventListener("drop", async (event) => {
            event.preventDefault();
            const id = event.dataTransfer.getData("text/plain");
            const draggedElement = document.getElementById(id);

            if (draggedElement) {
                dropzone.appendChild(draggedElement);
                
                const userId = id.replace("user", "");  // Extract user ID
                const groupContainer = dropzone.closest(".group-container");
                const groupId = groupContainer ? groupContainer.dataset.groupId : null;

                // Send an update request to the server
                await fetch("/update-user-group/", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": getCSRFToken()
                    },
                    body: JSON.stringify({ user_id: userId, group_id: groupId })
                })
                .then(response => response.json())
                .then(data => console.log("Update successful:", data))
                .catch(error => console.error("Error updating user group:", error));
            }
        });
    });

    function getCSRFToken() {
        return document.querySelector("[name=csrfmiddlewaretoken]").value;
    }
});
