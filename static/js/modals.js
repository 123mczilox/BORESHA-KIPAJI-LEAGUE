/* =========================================================
   BOREHSA KIPAJI LEAGUE
   MODAL MANAGEMENT
========================================================= */

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-open-modal]').forEach((trigger) => {
        trigger.addEventListener('click', () => {
            const selector = trigger.dataset.openModal;

            let modal;
            try {
                modal = document.querySelector(selector);
            } catch (error) {
                console.warn('Invalid modal selector:', selector);
                return;
            }

            if (!modal || typeof modal.showModal !== 'function' || modal.open) {
                return;
            }

            modal._lastTrigger = trigger;
            modal.showModal();
        });
    });

    document.querySelectorAll('dialog').forEach((modal) => {
        modal.querySelectorAll('[data-close-modal]').forEach((button) => {
            button.addEventListener('click', () => {
                modal.close(button.value || 'cancel');
            });
        });

        modal.addEventListener('click', (event) => {
            if (event.target === modal) {
                modal.close('cancel');
            }
        });

        modal.addEventListener('close', () => {
            document.dispatchEvent(new CustomEvent('confirmation-modal-close', {
                detail: {
                    modalId: modal.id,
                    returnValue: modal.returnValue,
                },
            }));

            if (modal._lastTrigger) {
                modal._lastTrigger.focus();
                return;
            }

            const trigger = modal.id
                ? document.querySelector(`[data-open-modal="#${modal.id}"]`)
                : null;

            if (trigger) trigger.focus();
        });
    });
});