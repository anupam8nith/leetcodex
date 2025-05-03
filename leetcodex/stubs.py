"""
leetcodex.stubs
A tiny bag of names LeetCode magically provides in its judge environment.
Importing this lets users omit them in their own source files.
"""
from typing import *        # List, Dict, Optional, Set, Tuple, DefaultDict ...

class ListNode:
    def __init__(self, val: int = 0, next: "ListNode | None" = None):
        self.val, self.next = val, next
    def __repr__(self):
        return f"ListNode({self.val})"

class TreeNode:
    def __init__(
        self, val: int = 0,
        left: "TreeNode | None" = None, right: "TreeNode | None" = None,
    ):
        self.val, self.left, self.right = val, left, right
    def __repr__(self):
        return f"TreeNode({self.val})"
