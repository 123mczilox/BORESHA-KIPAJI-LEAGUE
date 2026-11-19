/* =========================================================
   BOREHSA KIPAJI LEAGUE
   DASHBOARD SIDEBAR
========================================================= */

document.addEventListener('DOMContentLoaded', () => {

    const toggle = document.querySelector('.sidebar-toggle');
    const sidebar = document.querySelector('.dashboard-sidebar');

    if (!toggle || !sidebar) return;

    const mobileQuery = window.matchMedia('(max-width: 760px)');

    /**
     * Open or close the sidebar.
     */
    const setOpen = (isOpen) => {

        const isMobile = mobileQuery.matches;

        sidebar.classList.toggle('open', isOpen);
        toggle.setAttribute('aria-expanded', String(isOpen));

        toggle.setAttribute(
            'aria-label',
            isOpen ? 'Close sidebar' : 'Open sidebar'
        );

        if (isMobile) {
            sidebar.setAttribute('aria-hidden', String(!isOpen));
        } else {
            sidebar.removeAttribute('aria-hidden');
        }

        document.body.classList.toggle(
            'sidebar-open',
            isMobile && isOpen
        );

    };


    /**
     * Toggle sidebar visibility.
     */
    toggle.addEventListener('click', () => {

        const isOpen = sidebar.classList.contains('open');

        setOpen(!isOpen);

    });


    /**
     * Close sidebar after selecting a navigation link.
     */
    sidebar.addEventListener('click', (event) => {

        const link = event.target.closest('a');

        if (link && mobileQuery.matches) {
            setOpen(false);
        }

    });


    /**
     * Close sidebar when Escape is pressed.
     */
    document.addEventListener('keydown', (event) => {

        if (
            event.key === 'Escape' &&
            sidebar.classList.contains('open') &&
            mobileQuery.matches
        ) {

            setOpen(false);
            toggle.focus();

        }

    });


    /**
     * Close sidebar when clicking outside.
     */
    document.addEventListener('click', (event) => {

        if (
            mobileQuery.matches &&
            sidebar.classList.contains('open') &&
            !sidebar.contains(event.target) &&
            !toggle.contains(event.target)
        ) {

            setOpen(false);

        }

    });


    /**
     * Handle screen-size changes.
     */
    const handleViewportChange = () => {

        setOpen(false);

    };

    if (mobileQuery.addEventListener) {
        mobileQuery.addEventListener('change', handleViewportChange);
    } else {
        mobileQuery.addListener(handleViewportChange);
    }


    /**
     * Initial sidebar state.
     */
    setOpen(false);

});