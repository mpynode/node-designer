# Hex Attribute

Turns plain text into the space-separated hex string a Maya `type` node wants, so you can drive extruded text from live values. Here it prints a label plus a position, rounded.

The point is the output attribute type: `output` is a `hex` attribute, so the expression writes ordinary text and the encoding happens for you -- there is no manual unicode-to-hex step to write.

## Inputs

* `inPosition` -- the value printed into the string. Wire a transform's translate here.
* `decimals` -- how many decimal places each number is rounded to.

## Outputs

* `output` -- the encoded hex string. Wire it into a `type` node's text input.

## Create + Run demo

Builds an extruded Type text mesh whose parent transform is the handle -- drag it and the text redraws with its own X, Y and Z.
