# Finish the Monotaro bellows mount edges

- Added R2 plan corners and C0.4 perimeter breaks in Inventor to the three carriage plates, the table plate, and the thrust backing plate. Added C0.4 perimeter breaks to the thrust support block, TR16 holder and keeper. The guide spacer already had a fillet and chamfer.
- Set length, mass and time to mm, g and s in the eight edited parts. Checked successful rebuilds and unchanged overall bounding dimensions.
- Added a relative template folder override in PIHTI.ipj. Verified that a new part created directly from the project template reports mm, g and s, and that the project IDW template uses the JIS drawing standard. Unqualified FileManager.GetTemplateFile still returned the installed default, so automation should pass the project template path explicitly.
- Rechecked the four combinations of minimum and maximum bellows stage lengths in the Monotaro assembly. The front stayed fixed, the rear endpoints spanned 700 mm, and moving-to-fixed module interference results were empty. Refreshed the existing ISO review drawing.
