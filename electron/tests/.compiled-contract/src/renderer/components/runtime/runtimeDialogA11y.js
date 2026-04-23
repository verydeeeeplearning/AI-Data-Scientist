"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.createRuntimeDialogA11yController = createRuntimeDialogA11yController;
const focusManagement_1 = require("../../application/a11y/focusManagement");
function createRuntimeDialogA11yController(container, options = {}) {
    const trap = (0, focusManagement_1.createFocusTrap)(container, options);
    return {
        activate() {
            trap.activate();
        },
        deactivate() {
            trap.deactivate();
        },
        handleKeyDown(event) {
            if (event.key === 'Tab') {
                event.preventDefault();
                trap.cycle(event.shiftKey ? 'backward' : 'forward');
                return 'tab';
            }
            if (event.key === 'Escape') {
                event.preventDefault();
                return 'escape';
            }
            return null;
        },
    };
}
