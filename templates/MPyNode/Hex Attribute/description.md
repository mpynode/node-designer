# Hex Attribute

Turns plain text into the space-separated hex string a Maya `type` node wants. Here it prints a label plus `inPosition`, rounded to `decimals` places. The trick is the attribute type: `output` is a `hex` attr, so the expression writes ordinary text and it encodes itself -- no manual unicode->hex step. Wire `output` into a `type` node's text input.

**Create + Run demo** builds an extruded Type text mesh whose parent transform is the handle -- drag it and the text redraws with its own X/Y/Z.
