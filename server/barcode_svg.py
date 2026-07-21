# -*- coding: utf-8 -*-
"""توليد صورة SVG لباركود EAN-13 على الخادم (نفس منطق تطبيق سطح المكتب المُتحقَّق منه)."""

L_CODES = ["0001101", "0011001", "0010011", "0111101", "0100011",
           "0110001", "0101111", "0111011", "0110111", "0001011"]
G_CODES = ["0100111", "0110011", "0011011", "0100001", "0011101",
           "0111001", "0000101", "0010001", "0001001", "0010111"]
R_CODES = ["1110010", "1100110", "1101100", "1000010", "1011100",
           "1001110", "1010000", "1000100", "1001000", "1110100"]
STRUCTURE = ["LLLLLL", "LLGLGG", "LLGGLG", "LLGGGL", "LGLLGG",
             "LGGLLG", "LGGGLL", "LGLGLG", "LGLGGL", "LGGLGL"]


def generate_svg(full_code):
    """يعيد نص SVG لباركود EAN-13 من كود مكوّن من 13 خانة رقمية، أو None إن كان غير صالح."""
    if not full_code or len(full_code) != 13 or not full_code.isdigit():
        return None

    first_digit = int(full_code[0])
    left_digits = full_code[1:7]
    right_digits = full_code[7:]
    structure = STRUCTURE[first_digit]

    binary_string = "101"  # Start Guard
    for i in range(6):
        digit = int(left_digits[i])
        binary_string += L_CODES[digit] if structure[i] == 'L' else G_CODES[digit]
    binary_string += "01010"  # Center Guard
    for i in range(6):
        binary_string += R_CODES[int(right_digits[i])]
    binary_string += "101"  # End Guard

    module_width = 2
    short_bar_height = 110
    long_bar_height = 123
    font_size = 20
    total_width = (10 + len(binary_string) + 7) * module_width  # 10 يسار + 95 قضيباً + 7 يمين
    total_height = long_bar_height + 10
    start_x = 10 * module_width

    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" '
           f'height="{total_height}" viewBox="0 0 {total_width} {total_height}">\n')
    svg += '<rect width="100%" height="100%" fill="white"/>\n'
    for i, bit in enumerate(binary_string):
        if bit == '1':
            x = start_x + (i * module_width)
            is_guard = (i < 3) or (i >= 45 and i < 50) or (i >= 92)
            h = long_bar_height if is_guard else short_bar_height
            svg += (f'<rect x="{x}" y="0" width="{module_width}" height="{h}" '
                    f'fill="black" shape-rendering="crispEdges"/>\n')

    text_y = long_bar_height + 2
    svg += (f'<text x="{start_x - 10}" y="{text_y}" font-family="monospace" '
            f'font-size="{font_size}" text-anchor="end">{first_digit}</text>\n')
    left_x_str = start_x + (3 * module_width) + (3.5 * module_width)
    for i, d in enumerate(left_digits):
        x = left_x_str + (i * 7 * module_width)
        svg += (f'<text x="{x}" y="{text_y}" font-family="monospace" '
                f'font-size="{font_size}" text-anchor="middle">{d}</text>\n')
    right_x_str = start_x + (50 * module_width) + (3.5 * module_width)
    for i, d in enumerate(right_digits):
        x = right_x_str + (i * 7 * module_width)
        svg += (f'<text x="{x}" y="{text_y}" font-family="monospace" '
                f'font-size="{font_size}" text-anchor="middle">{d}</text>\n')
    svg += (f'<text x="{start_x + (95 * module_width) + 10}" y="{text_y}" font-family="monospace" '
            f'font-size="{font_size}" text-anchor="start">&gt;</text>\n')
    svg += '</svg>'
    return svg
