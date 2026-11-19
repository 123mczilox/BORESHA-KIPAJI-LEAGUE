document.addEventListener('DOMContentLoaded', () => {
    const toggle = document.querySelector('.nav-toggle');
    const navigation = document.querySelector('.nav-links');

    if (toggle && navigation) {
        toggle.addEventListener('click', () => {
            const isOpen = navigation.classList.toggle('open');
            toggle.setAttribute('aria-expanded', String(isOpen));
            toggle.setAttribute('aria-label', isOpen ? 'Close navigation' : 'Open navigation');
        });

        navigation.addEventListener('click', (event) => {
            if (event.target.closest('a')) {
                navigation.classList.remove('open');
                toggle.setAttribute('aria-expanded', 'false');
                toggle.setAttribute('aria-label', 'Open navigation');
            }
        });

        document.addEventListener('click', (event) => {
            if (!event.target.closest('.public-nav')) {
                navigation.classList.remove('open');
                toggle.setAttribute('aria-expanded', 'false');
            }
        });

        window.addEventListener('resize', () => {
            if (window.innerWidth > 760) {
                navigation.classList.remove('open');
                toggle.setAttribute('aria-expanded', 'false');
            }
        });
    }

    const navLinks = [...document.querySelectorAll('.nav-link')];

    const setActiveByPath = () => {
        const path = window.location.pathname;

        navLinks.forEach((link) => {
            const href = link.getAttribute('href') || '';
            let isActive = false;

            if (href === '/') {
                isActive = path === '/' && !window.location.hash;
            } else if (href.startsWith('/#')) {
                isActive = path === '/' && window.location.hash === href.substring(1);
            } else if (href.includes('/teams/')) {
                isActive = path.startsWith('/teams/');
            } else if (href.includes('/players/')) {
                isActive = path.startsWith('/players/');
            } else if (href === '/#standings' || href.includes('/standings/')) {
                isActive = path.startsWith('/standings/') || (path === '/' && window.location.hash === '#standings');
            } else if (href.includes('/about/')) {
                isActive = path.startsWith('/about/');
            }

            link.classList.toggle('active', isActive);
            if (isActive) {
                link.setAttribute('aria-current', href === '/' ? 'page' : 'location');
            } else {
                link.removeAttribute('aria-current');
            }
        });
    };

    setActiveByPath();
    const sectionLinks = navLinks.filter((link) => {
        const href = link.getAttribute('href') || '';
        return href === '/' || href === '/about/' || href.startsWith('/#') || href.startsWith('#');
    });

    const setActiveLink = (id) => {
        sectionLinks.forEach((link) => {
            const href = link.getAttribute('href') || '';
            const targetId = href === '/' ? 'home' : href === '/about/' ? 'about' : href.split('#')[1] || '';
            const isActive = targetId === id;

            link.classList.toggle('active', isActive);
            if (isActive) {
                link.setAttribute('aria-current', 'location');
            } else {
                link.removeAttribute('aria-current');
            }
        });
    };

    const trackedSections = ['about', 'fixtures', 'results', 'standings', 'news']
        .map((id) => document.getElementById(id))
        .filter(Boolean);

    let scrollFrame = null;

    const updateActiveSection = () => {
        scrollFrame = null;

        if (window.location.pathname !== '/') {
            setActiveByPath();
            return;
        }

        const marker = window.scrollY + 180;
        let activeId = 'home';

        trackedSections.forEach((section) => {
            if (section.offsetTop <= marker) {
                activeId = section.id;
            }
        });

        setActiveLink(activeId);
    };

    const requestActiveUpdate = () => {
        if (scrollFrame === null) {
            scrollFrame = window.requestAnimationFrame(updateActiveSection);
        }
    };

    window.addEventListener('scroll', requestActiveUpdate, { passive: true });
    window.addEventListener('hashchange', setActiveByPath);
    window.addEventListener('resize', requestActiveUpdate);
    updateActiveSection();
});
