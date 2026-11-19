/* =========================================================
   BOREHSA KIPAJI LEAGUE
   TABLE MANAGEMENT
========================================================= */

document.addEventListener('DOMContentLoaded', () => {

    document.querySelectorAll('.table-wrap table').forEach((table) => {

        // Preserve native HTML table semantics.
        table.setAttribute('data-table-ready', 'true');

        // Only enable sorting on tables explicitly marked sortable.
        if (!table.hasAttribute('data-sortable')) {
            return;
        }

        const headers = table.querySelectorAll('thead th');

        headers.forEach((header, columnIndex) => {

            if (header.hasAttribute('data-no-sort')) {
                return;
            }

            header.style.cursor = 'pointer';
            header.setAttribute('tabindex', '0');
            header.setAttribute('role', 'button');
            header.setAttribute('aria-label',
                `${header.textContent.trim()}, sort table`
            );

            const sortTable = () => {

                const tbody = table.querySelector('tbody');

                if (!tbody) return;

                const rows = Array.from(tbody.querySelectorAll('tr'));

                const ascending =
                    header.getAttribute('aria-sort') !== 'ascending';

                headers.forEach((item) => {
                    item.removeAttribute('aria-sort');
                });

                header.setAttribute(
                    'aria-sort',
                    ascending ? 'ascending' : 'descending'
                );

                rows.sort((rowA, rowB) => {

                    const valueA =
                        rowA.cells[columnIndex]?.textContent.trim() || '';

                    const valueB =
                        rowB.cells[columnIndex]?.textContent.trim() || '';

                    const numberA = Number(valueA.replace(/,/g, ''));
                    const numberB = Number(valueB.replace(/,/g, ''));

                    if (valueA !== '' && valueB !== '' &&
                        !Number.isNaN(numberA) && !Number.isNaN(numberB)) {

                        return ascending
                            ? numberA - numberB
                            : numberB - numberA;
                    }

                    return ascending
                        ? valueA.localeCompare(valueB)
                        : valueB.localeCompare(valueA);

                });

                rows.forEach((row) => tbody.appendChild(row));

            };

            header.addEventListener('click', sortTable);

            header.addEventListener('keydown', (event) => {

                if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    sortTable();
                }

            });

        });

    });

});