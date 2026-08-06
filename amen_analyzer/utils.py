class History:
    """Undo/redo stack of onset-list snapshots."""

    def __init__(self, initial_state):
        self.undo_stack = [list(initial_state)]
        self.redo_stack = []

    def push(self, state):
        self.undo_stack.append(list(state))
        self.redo_stack.clear()

    def undo(self):
        if len(self.undo_stack) < 2:
            return None
        self.redo_stack.append(self.undo_stack.pop())
        return list(self.undo_stack[-1])

    def redo(self):
        if not self.redo_stack:
            return None
        state = self.redo_stack.pop()
        self.undo_stack.append(state)
        return list(state)
