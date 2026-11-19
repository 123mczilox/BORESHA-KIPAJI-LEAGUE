/* =========================================================
   BOREHSA KIPAJI LEAGUE
   MAIN JAVASCRIPT
========================================================= */

document.addEventListener('DOMContentLoaded', () => {


    /* =====================================================
       2. DASHBOARD PROFILE DROPDOWN
    ===================================================== */

    const profileToggle = document.querySelector('.topbar-user-button');
    const profileMenu = document.querySelector('.topbar-user-menu');

    const closeNotificationMenu = () => {

        const notificationButton = document.querySelector('.notification-button');
        const notificationDropdown = document.querySelector('.notification-dropdown');

        if (notificationDropdown && notificationButton) {

            notificationDropdown.hidden = true;

            notificationButton.setAttribute('aria-expanded', 'false');

            notificationButton.classList.remove('active');

        }

    };

    if (profileToggle && profileMenu) {

        const setProfileOpen = (isOpen) => {

            profileMenu.hidden = !isOpen;

            profileToggle.setAttribute('aria-expanded', String(isOpen));

            if (isOpen) {
                closeNotificationMenu();
            }

        };


        /* Toggle profile menu */

        profileToggle.addEventListener('click', (event) => {

            event.stopPropagation();

            const willOpen = profileMenu.hidden;
            setProfileOpen(willOpen);

            if (willOpen) {
                const firstEnabledItem = profileMenu.querySelector(
                    'a:not([aria-disabled="true"]), button:not(:disabled)' 
                );

                if (firstEnabledItem) {
                    firstEnabledItem.focus();
                }
            }

        });


        /* Close when clicking outside */

        document.addEventListener('click', (event) => {

            if (!event.target.closest('.topbar-profile')) {

                setProfileOpen(false);

            }

        });


        /* Close with Escape */

        document.addEventListener('keydown', (event) => {

            if (event.key === 'Escape' && !profileMenu.hidden) {

                setProfileOpen(false);

                profileToggle.focus();

            }

        });


        /* Keyboard navigation */

        profileMenu.addEventListener('keydown', (event) => {

            if (
                event.key === 'ArrowDown' ||
                event.key === 'ArrowUp'
            ) {

                const items = [
                    ...profileMenu.querySelectorAll(
                        'a:not([aria-disabled="true"]), button:not(:disabled)'
                    )
                ];

                if (!items.length) return;

                event.preventDefault();

                const currentIndex = items.indexOf(document.activeElement);

                const direction = event.key === 'ArrowDown' ? 1 : -1;

                const nextIndex = currentIndex === -1
                    ? (direction === 1 ? 0 : items.length - 1)
                    : (currentIndex + direction + items.length) % items.length;

                items[nextIndex].focus();

            }

        });

    }


    /* =====================================================
       3. DASHBOARD SEARCH SHORTCUT
    ===================================================== */

    const searchForm = document.querySelector('.topbar-search');

    const searchInput = searchForm?.querySelector(
        'input[type="search"]'
    );

    if (searchForm && searchInput) {

        /*
         * Search is currently visual only.
         * Prevent accidental page reload until an existing
         * search endpoint is connected.
         */

        searchForm.addEventListener('submit', (event) => {

            event.preventDefault();

        });


        /*
         * Press "/" to focus search.
         */

        document.addEventListener('keydown', (event) => {

            const activeElement = document.activeElement;

            const isTyping = activeElement &&
                ['INPUT', 'TEXTAREA', 'SELECT'].includes(activeElement.tagName);

            if (
                event.key === '/' &&
                !event.metaKey &&
                !event.ctrlKey &&
                !event.altKey &&
                !isTyping
            ) {

                event.preventDefault();

                searchInput.focus();

            }

        });

    }

});