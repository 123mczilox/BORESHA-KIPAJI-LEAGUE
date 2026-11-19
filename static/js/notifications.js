/* =========================================================
   BOREHSA KIPAJI LEAGUE
   NOTIFICATION DROPDOWN
========================================================= */

document.addEventListener('DOMContentLoaded', () => {

    const wrappers = document.querySelectorAll('.notification-wrapper');

    wrappers.forEach((wrapper) => {

        const button = wrapper.querySelector('.notification-button');
        const dropdown = wrapper.querySelector('.notification-dropdown');

        if (!button || !dropdown) return;


        /**
         * Close the profile dropdown.
         */
        const closeProfileMenu = () => {

            const profileToggle = document.querySelector('.topbar-user-button');
            const profileMenu = document.querySelector('.topbar-user-menu');

            if (profileToggle && profileMenu) {
                profileMenu.hidden = true;
                profileToggle.setAttribute('aria-expanded', 'false');
            }

        };


        /**
         * Open or close notifications.
         */
        const setOpen = (isOpen) => {

            dropdown.hidden = !isOpen;

            button.setAttribute('aria-expanded', String(isOpen));

            button.classList.toggle('active', isOpen);

            if (isOpen) {
                closeProfileMenu();
            }

        };


        /**
         * Toggle notification dropdown.
         */
        button.addEventListener('click', (event) => {

            event.stopPropagation();

            setOpen(dropdown.hidden);

        });


        /**
         * Close when clicking outside.
         */
        document.addEventListener('click', (event) => {

            if (!wrapper.contains(event.target)) {
                setOpen(false);
            }

        });


        /**
         * Close when Escape is pressed.
         */
        document.addEventListener('keydown', (event) => {

            if (event.key === 'Escape' && !dropdown.hidden) {

                setOpen(false);

                button.focus();

            }

        });

    });

});