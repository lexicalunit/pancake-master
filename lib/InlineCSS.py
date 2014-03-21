from bs4 import BeautifulSoup


def apply_style(tag, tag_style):
    """Inlines the given tag style to the given tag's style attribute."""
    if 'style' not in tag.attrs:
        tag['style'] = ''
    s = ''.join('{}: {};'.format(k, v) for k, v in tag_style.items())
    tag['style'] += s


def pseudoclass_applies(tag, pseudoclass):
    """Returns True iff the given pseudo-class name applies to the given tag."""
    # TODO: Support more CSS pseudo-classes.
    nth_child = tag.parent.index(tag)
    if pseudoclass == 'nth-child(even)' and nth_child % 2 == 0:
        return True
    elif pseudoclass == 'nth-child(odd)' and nth_child % 2 != 0:
        return True
    elif pseudoclass == 'first-child' and nth_child == 0:
        return True
    elif pseudoclass == 'last-child' and nth_child + 1 == len([c for c in tag.parent.children]):
        return True
    return False


def styled(html, style):
    """Returns inline CSS styled HTML."""

    def as_string(soup):
        return str(soup.prettify())

    soup = BeautifulSoup(html)

    if not style:
        return as_string(soup)

    def split_key(key):
        """Helper: Splits CSS key into selector and list of available pseudo-classes."""
        pair = key.split(':')
        if len(pair) == 1:
            return (pair[0], [])
        return tuple(pair)

    selectors = {}
    for key in style.keys():
        selector, pseudoclass = split_key(key)
        if selector not in selectors:
            selectors[selector] = []
        if pseudoclass:
            selectors[selector].append(pseudoclass)

    def selector_applies(selector, tag):
        """Helper: Returns true iff the given selector specification applies to the given tag."""
        # TODO: Support more complicated CSS selectors.
        if ' ' in selector:
            parent, inner_selector = selector.split(' ')
        else:
            parent, inner_selector = None, selector

        if parent:
            if not selector_applies(parent, tag.parent):
                return False

        if tag.name == inner_selector:
            return True

        for tag_class in tag.get('class', []):
            if inner_selector == '.' + tag_class:
                return True

        if 'id' in tag.attrs and inner_selector == '#' + tag['id']:
                return True

        return False


    def get_tag_style(tag, style, selectors):
        """Helper: Gets the tag's style give the complete CSS style and selectors lookup."""
        keys = []
        for selector in selectors:
            if selector_applies(selector, tag):
                keys.append(selector)

        tag_style = {}
        for key in keys:
            if key in style:
                tag_style.update(style[key])
            if selectors[key]:
                for pseudoclass in selectors[key]:
                    if pseudoclass_applies(tag, pseudoclass):
                        tag_style.update(style[key + ':' + pseudoclass])

        return tag_style

    for tag in soup.find_all(True):
        apply_style(tag, get_tag_style(tag, style, selectors))

    return as_string(soup)
