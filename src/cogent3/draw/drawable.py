import os
import pathlib

import numpy

from cogent3.util.misc import extend_docstring_from
from cogent3.util.union_dict import UnionDict


__author__ = "Rahul Ghangas and Gavin Huttley"
__copyright__ = "Copyright 2007-2020, The Cogent Project"
__credits__ = ["Rahul Ghangas", "Gavin Huttley"]
__license__ = "BSD-3"
__version__ = "2020.2.7a"
__maintainer__ = "Gavin Huttley"
__email__ = "gavin.huttley@anu.edu.au"
__status__ = "Alpha"

# user specified environment variable for plotly renderer
PLOTLY_RENDERER = os.environ.get("PLOTLY_RENDERER", None)


def get_domain(total, element, is_y, space=0.01):
    """returns evenly spaced domain for an element in a grid plot

    Parameters
    ----------
    total : int
        the total number of elements on the axis
    element : int
        the element number to compute the domain for
    is_y : bool
        if True, this is for a y-coordinate domain. This is reversed
        so the result is in cartesian, not array, coordinates
    space : float
        the separation between elements
    """
    if total == 1:
        return [0, 1]

    if element > total - 1:
        raise ValueError(f"{element} index too big for {total}")

    per_element = 1 / total
    space = min(space / 2, per_element / 10)
    bounds = [per_element * i for i in range(total + 1)]
    domains = [
        (bounds[k] + space, bounds[k + 1] - space) for k in range(len(bounds) - 1)
    ]
    if is_y:
        element = total - element - 1

    return domains[element]


def _customise_sphinx_gallery_renderer():
    # this is an ugly hack to get around plotly's NOT robust handling of script path
    # for automated file naming
    import inspect
    from plotly.io._renderers import renderers
    from plotly.io import _base_renderers as base_render

    class SphinxGalleryRenderer(base_render.ExternalRenderer):
        def render(self, fig_dict):
            # use the environment variable
            # DOCUTILSCONFIG to get the location of the sphinx root doc dir
            # and select the stack filename whose path is a sibling directory
            # based on the maxinum number of matches to the root path
            sphinx_root = pathlib.Path(os.environ.get("DOCUTILSCONFIG", "")).absolute()
            sphinx_root = sphinx_root.resolve()
            stack = inspect.stack()
            max_match = 0
            for level in stack:
                # parent directory
                path = pathlib.Path(level.filename).absolute().resolve()
                for i, (a, b) in enumerate(zip(path.parts, sphinx_root.parts)):
                    if a != b:
                        break

                if i > max_match:
                    max_match = i
                    filename = str(path)

            filename_root, _ = os.path.splitext(filename)
            filename_html = filename_root + ".html"
            filename_png = filename_root + ".png"
            figure = base_render.return_figure_from_figure_or_data(fig_dict, True)
            _ = base_render.write_html(fig_dict, file=filename_html)
            base_render.write_image(figure, filename_png)

    renderers["sphinx_gallery"] = SphinxGalleryRenderer()


def _show_(cls, renderer=None, **kwargs):
    """display figure

    Parameters
    ----------
    renderer : str
        names of renderers that control ability for display. If not specified,
        looks for PLOTLY_RENDERER environment variable, otherwise defaults to
        'notebook_connected+plotly_mimetype'. This setting supports display in
        JupyterLab and Jupyter Notebook, while keeping notebook size small (relies
        on internet connection for getting the javascript). See
        help(plotly.io.renderer) for more options.
    kwargs
        other arguments for plotly.io.show
    """
    from plotly.io import show

    if renderer is None and PLOTLY_RENDERER is None:
        renderer = "notebook_connected+plotly_mimetype"
    elif renderer is None:
        renderer = PLOTLY_RENDERER

    if renderer == "sphinx_gallery":
        _customise_sphinx_gallery_renderer()

    kwargs["renderer"] = renderer
    drawable = getattr(cls, "drawable", None) or cls
    fig = getattr(drawable, "figure", None)
    if fig is None:
        raise TypeError(f"{cls} does not have a drawable or figure attribute")

    width = kwargs.get("width", fig.layout.width)
    height = kwargs.get("height", fig.layout.height)
    kwargs["width"] = fig.layout.width = width
    kwargs["height"] = fig.layout.height = height
    show(fig, **kwargs)


def _iplot_(cls, width=None, height=None):
    from plotly.offline import iplot as _iplot

    layout = {}
    if width:
        layout["width"] = width
    if height:
        layout["height"] = height
    if layout:
        cls.drawable.layout |= dict(layout)
    _iplot(cls.drawable.figure)


def bind_drawable(obj, drawable):
    """binds drawable"""
    from types import MethodType

    obj.drawable = drawable
    obj.iplot = MethodType(_iplot_, obj)
    obj.show = MethodType(_show_, obj)
    return obj


class Drawable:
    """container object for Plotly figures"""

    def __init__(
        self,
        title=None,
        traces=None,
        width=None,
        height=None,
        showlegend=True,
        visible_axes=True,
        layout=None,
        xtitle=None,
        ytitle=None,
    ):
        self._traces = traces or []
        title = title if title is None else dict(text=title)
        self._default_layout = UnionDict(
            font=dict(family="Balto", size=14),
            autosize=False,
            hovermode="closest",
            template=None,
            plot_bgcolor=None,
            margin=dict(l=50, r=50, t=50, b=50, pad=4),
            xaxis=dict(visible=visible_axes),
            yaxis=dict(visible=visible_axes),
            title=title,
            width=width,
            height=height,
            showlegend=showlegend,
        )
        layout = layout or {}
        self.layout = UnionDict(self._default_layout)
        self.layout |= layout
        # constructor layout value over-rides
        overrides = UnionDict(
            title=title,
            width=width,
            height=height,
            showlegend=showlegend,
            xaxis=dict(visible=visible_axes),
            yaxis=dict(visible=visible_axes),
        )
        self.layout |= overrides
        self.xtitle = xtitle
        self.ytitle = ytitle
        self.title = title

    def _repr_html_(self):
        self.show()

    @property
    def traces(self):
        return self._traces

    def get_trace_titles(self):
        titles = [tr.name for tr in self.traces]
        return titles

    def pop_trace(self, title):
        """removes the trace with a matching title attribute"""
        try:
            index = self.get_trace_titles().index(title)
        except ValueError:
            UserWarning(f"no trace with name {title}")
            return

        return self.traces.pop(index)

    def remove_traces(self, names):
        """removes traces by name

        Parameters
        ----------
        names : str or iterable of str
            trace names

        """
        if not self.traces:
            self._build_fig()

        names = names if type(names) != str else [names]
        for name in names:
            _ = self.pop_trace(name)

    def add_trace(self, trace):
        self.traces.append(trace)

    def bound_to(self, obj):
        """returns obj with self bound to it"""
        return bind_drawable(obj, self)

    @property
    def figure(self):
        if not self.traces and hasattr(self, "_build_fig"):
            self._build_fig()

        traces = self.traces if self.traces else [{}]

        if self.xtitle:
            xtitle = self.xtitle
        else:
            xtitle = self.layout.xaxis.get("title", None)

        if self.ytitle:
            ytitle = self.ytitle
        else:
            ytitle = self.layout.yaxis.get("title", None)

        self.layout.xaxis.title = xtitle
        self.layout.yaxis.title = ytitle
        return UnionDict(data=traces, layout=self.layout)

    def iplot(self, *args, **kwargs):
        from plotly.offline import iplot as _iplot

        _iplot(self.figure, *args, **kwargs)

    @extend_docstring_from(_show_)
    def show(self, renderer=None, **kwargs):
        _show_(self, renderer, **kwargs)

    def write(self, path, **kwargs):
        """writes static image file, suffix dictates format"""
        from plotly.io import write_image

        fig = self.figure
        kwargs["width"] = kwargs.get("width", fig.layout.width)
        kwargs["height"] = kwargs.get("height", fig.layout.height)

        write_image(fig, path, **kwargs)

    def to_image(self, format="png", **kwargs):
        """creates static image, suffix dictates format"""
        from plotly.io import to_image

        fig = self.figure
        kwargs["width"] = kwargs.get("width", fig.layout.width)
        kwargs["height"] = kwargs.get("height", fig.layout.height)

        return to_image(fig, format=format, **kwargs)

    @property
    def fig_width(self):
        """figure width, also settable via .layout.width"""
        return self.layout.width

    @fig_width.setter
    def fig_width(self, width):
        self.layout.width = width

    @property
    def fig_height(self):
        """figure height, also settable via .layout.height"""
        return self.layout.height

    @fig_height.setter
    def fig_height(self, height):
        self.layout.height = height


_ticks_off = (
    ("showticklabels", False),
    ("mirror", True),
    ("showgrid", False),
    ("showline", True),
    ("ticks", ""),
)

_ticks_on = (
    ("showticklabels", True),
    ("mirror", True),
    ("showgrid", False),
    ("showline", True),
)


class AnnotatedDrawable(Drawable):
    """supports drawing with left and bottom tracks of annotations"""

    def __init__(
        self,
        core,
        left_track=None,
        bottom_track=None,
        xtitle=None,
        ytitle=None,
        title=None,
        xrange=None,
        yrange=None,
        width=500,
        height=500,
        layout=None,
    ):
        super(AnnotatedDrawable, self).__init__(
            visible_axes=True,
            showlegend=True,
            width=width,
            height=height,
            layout=layout,
        )

        self.xtitle = xtitle
        self.ytitle = ytitle
        self.yrange = yrange
        self.xrange = xrange
        self._overlaying = False

        core.title = title or core.title
        self.core = core
        self.left_track = left_track
        self.bottom_track = bottom_track

    def _build_fig(self, xaxis="x", yaxis="y"):
        f = self.core.figure
        try:
            if self.layout.yaxis2.overlaying != "free":
                self._overlaying = True
        except AttributeError:
            pass

        try:
            traces = f.traces
            self.layout |= dict(f.layout)
        except AttributeError:
            traces = f["data"]
            self.layout |= f["layout"]
        for trace in traces:
            trace.xaxis = xaxis
            if self._overlaying and "yaxis" in trace:
                trace.yaxis = "y3"
            else:
                trace.yaxis = yaxis
        self._traces = traces
        ticks_on = dict(_ticks_on)
        f.layout.xaxis.title = self.xtitle
        f.layout.yaxis.title = self.ytitle
        f.layout.xaxis |= ticks_on
        f.layout.yaxis |= ticks_on
        return f

    def _build_2x2_fig(self):
        if not self.traces:
            _ = self._build_fig(xaxis="x2", yaxis="y2")

        layout = UnionDict(
            {
                "xaxis": {"anchor": "y", "domain": [0.0, 0.099]},
                "xaxis2": {"anchor": "y2", "domain": [0.109, 1.0]},
                "xaxis3": {"anchor": "y3", "domain": [0.109, 1.0]},
                "yaxis": {"anchor": "x", "domain": [0.109, 1.0]},
                "yaxis2": {"anchor": "x2", "domain": [0.109, 1.0]},
                "yaxis3": {"anchor": "x3", "domain": [0.0, 0.099]},
            }
        )
        layout |= self.layout
        fig = UnionDict(data=[], layout=layout)

        # common settings
        ticks_off_kwargs = dict(_ticks_off)
        ticks_on_kwargs = dict(_ticks_on)

        # core traces and layout
        fig.data.extend(self.traces)

        fig.layout.xaxis2 |= dict(range=self.xrange, **ticks_off_kwargs)
        fig.layout.yaxis2 |= dict(range=self.yrange, **ticks_off_kwargs)

        # left_track traces
        seen_types = set()
        max_x = 0
        traces = []
        for trace in self.left_track.traces:
            traces.append(trace)
            # convert to numpy array to handle None's
            x = numpy.array(trace.x, dtype=float)
            indices = numpy.logical_not(numpy.isnan(x))
            max_x = max(x[indices].max(), max_x)
            if trace.legendgroup in seen_types:
                trace.showlegend = False
            seen_types.add(trace.legendgroup)

        left_range = [0, int(max_x) + 1]

        # bottom_track traces
        max_y = 0
        for trace in self.bottom_track.traces:
            trace.xaxis = "x3"
            trace.yaxis = "y3"
            traces.append(trace)
            # convert to numpy array to handle None's
            y = numpy.array(trace.y, dtype=float)
            indices = numpy.logical_not(numpy.isnan(y))
            max_y = max(y[indices].max(), max_y)
            if trace.legendgroup in seen_types:
                trace.showlegend = False
            seen_types.add(trace.legendgroup)

        bottom_range = [0, int(max_y) + 1]

        # add all traces
        fig.data.extend(traces)
        # configure axes for titles, limits, border and ticks
        fig.layout.yaxis |= dict(
            title=dict(text=self.ytitle), range=self.yrange, **ticks_on_kwargs
        )

        fig.layout.xaxis3 |= dict(
            title=dict(text=self.xtitle), range=self.xrange, **ticks_on_kwargs
        )

        # adjust row width of left plot for number of feature tracks
        min_range = min(left_range[1], bottom_range[1])
        left_prop = left_range[1] / min_range

        # first the top row
        xaxis_domain = list(layout.xaxis.domain)
        xaxis_domain[1] = left_prop * xaxis_domain[1]
        fig.layout.xaxis |= dict(
            title=None, range=left_range, domain=xaxis_domain, **ticks_off_kwargs
        )
        fig.layout.xaxis |= dict(
            title={}, range=left_range, domain=xaxis_domain, **ticks_off_kwargs
        )

        space = 0.01
        fig.layout.xaxis2.domain = (xaxis_domain[1] + space, 1.0)
        fig.layout.xaxis3.domain = (xaxis_domain[1] + space, 1.0)

        # now the right column
        bottom_prop = bottom_range[1] / min_range
        yaxis_domain = list(layout.yaxis3.domain)
        yaxis_domain[1] = bottom_prop * yaxis_domain[1]
        fig.layout.yaxis3 |= dict(
            title={}, range=bottom_range, domain=yaxis_domain, **ticks_off_kwargs
        )

        # and bottom of the boxes above
        fig.layout.yaxis.domain = (yaxis_domain[1] + space, 1.0)
        fig.layout.yaxis2.domain = (yaxis_domain[1] + space, 1.0)

        return fig

    def _build_2x1_fig(self):
        """2 rows, one column, dotplot and seq1 annotated"""
        if not self.traces:
            _ = self._build_fig()

        layout = UnionDict(
            xaxis={"anchor": "y2", "domain": [0.0, 1.0]},
            yaxis={"anchor": "free", "domain": [0.1135, 1.0], "position": 0.0},
            yaxis2={"anchor": "x", "domain": [0.0, 0.0985]},
        )
        if self._overlaying:
            self.layout.yaxis3 = self.layout.yaxis2
            self.layout.yaxis2 = {}
            self.layout.legend.x = 1.3
        layout |= dict(self.layout)
        fig = UnionDict(data=[], layout=layout)

        # common settings
        ticks_off_kwargs = dict(_ticks_off)
        ticks_on_kwargs = dict(_ticks_on)

        # core traces and layout
        fig.data.extend(self.traces)

        fig.layout.xaxis |= dict(
            title=dict(text=self.xtitle), range=self.xrange, **ticks_on_kwargs
        )
        fig.layout.yaxis |= dict(
            title=dict(text=self.ytitle), range=self.yrange, **ticks_on_kwargs
        )

        # bottom traces
        seen_types = set()
        max_y = 0
        traces = []
        for trace in self.bottom_track.traces:
            trace.yaxis = "y2"
            trace.xaxis = "x"
            traces.append(trace)
            y = numpy.array(trace.y, dtype=float)
            indices = numpy.logical_not(numpy.isnan(y))
            max_y = max(y[indices].max(), max_y)
            if trace.legendgroup in seen_types:
                trace.showlegend = False
            seen_types.add(trace.legendgroup)

        fig.data.extend(traces)
        fig.layout.yaxis2 |= dict(
            title={}, range=[0, int(max_y) + 1], **ticks_off_kwargs
        )
        return fig

    def _build_1x2_fig(self):
        if not self.traces:
            self._build_fig(xaxis="x2")
        layout = UnionDict(
            xaxis={"anchor": "y", "domain": [0.0, 0.099]},
            xaxis2={"anchor": "free", "domain": [0.109, 1.0], "position": 0.0},
            yaxis={"anchor": "x", "domain": [0.0, 1.0]},
        )

        layout |= self.layout
        fig = UnionDict(data=[], layout=layout)

        # common settings
        ticks_off_kwargs = dict(_ticks_off)
        ticks_on_kwargs = dict(_ticks_on)

        # core traces and layout
        fig.data.extend(self.traces)

        fig.layout.xaxis2 |= dict(
            title=self.xtitle, range=self.xrange, **ticks_on_kwargs
        )
        fig.layout.yaxis |= dict(
            title=self.ytitle, range=self.yrange, **ticks_on_kwargs
        )

        # left track
        seen_types = set()
        max_x = 0
        traces = []
        for trace in self.left_track.traces:
            trace.yaxis = "y"
            traces.append(trace)
            x = numpy.array(trace.x, dtype=float)
            indices = numpy.logical_not(numpy.isnan(x))
            max_x = max(x[indices].max(), max_x)
            if trace.legendgroup in seen_types:
                trace.showlegend = False
            seen_types.add(trace.legendgroup)

        fig.data.extend(traces)
        fig.layout.xaxis |= dict(
            title=None, range=[0, int(max_x) + 1], **ticks_off_kwargs
        )
        return fig

    @property
    def figure(self):
        if self.bottom_track and self.left_track:
            func = self._build_2x2_fig
        elif self.bottom_track:
            func = self._build_2x1_fig
        elif self.left_track:
            func = self._build_1x2_fig
        else:
            func = self._build_fig

        result = func()

        return result

    def remove_track(self, left_track=False, bottom_track=False):
        """
        Parameters
        ----------
        left_track : bool
            the left track is removed
        bottom_track : bool
            the bottom track is removed
        """
        if left_track:
            self.left_track = None

        if bottom_track:
            self.bottom_track = None

        if left_track or bottom_track:
            self.core._traces = []
            self._traces = []


class Shape:
    _mode = "lines"

    def __init__(
        self,
        name=None,
        text=None,
        filled=True,
        legendgroup=None,
        showlegend=True,
        hoverinfo=None,
        fillcolor=None,
    ):
        self.filled = filled
        self.fillcolor = fillcolor
        self._legendgroup = legendgroup
        self._showlegend = showlegend
        self.name = name
        self.text = text
        self._hoverinfo = hoverinfo or name

    def shift(self, x=0, y=0):
        if not isinstance(self.x, numpy.ndarray):
            self.x += x
            self.y += y
        else:
            self.x[self.x != None] += x
            self.y[self.y != None] += y

        return self

    @property
    def height(self):
        return self.top - self.bottom

    @property
    def top(self):
        if not isinstance(self.y, numpy.ndarray):
            return numpy.max(self.y)
        else:
            return numpy.max(self.y[self.y != None])

    @property
    def bottom(self):
        if not isinstance(self.y, numpy.ndarray):
            return numpy.min(self.y)
        else:
            return numpy.min(self.y[self.y != None])

    @property
    def middle(self):
        return self.height / 2 + self.bottom

    @property
    def T(self):
        self.x, self.y = self.y, self.x
        return self

    def as_trace(self, name=None):
        """returns component for plotly display"""
        name = name or self.name
        data = UnionDict(
            type="scatter",
            x=self.x,
            y=self.y,
            mode=self._mode,
            fill="toself",
            fillcolor=self.fillcolor,
            line=dict(color=self.fillcolor),
            text=self.text,
            name=name,
            legendgroup=self._legendgroup,
            showlegend=self._showlegend,
            hoverinfo="text",
        )
        return data


class Rectangle(Shape):
    def __init__(self, coords, y=0, height=0.25, **kwargs):
        super(Rectangle, self).__init__(**kwargs)
        width = abs(coords[0][0] - coords[0][1])
        x_coord = min(coords[0][0], coords[0][1])
        xs = [x_coord, x_coord, x_coord + width, x_coord + width, x_coord]
        ys = [y, y + height, y + height, y, y]
        for i in range(1, len(coords)):
            # Add coordinates for connecting line segment
            xs += [None, coords[i - 1][1], coords[i][0], None]
            ys += [None, y + height / 2, y + height / 2, None]
            # Add coordinates for individual rectangle
            width = abs(coords[i][0] - coords[i][1])
            x_coord = min(coords[i][0], coords[i][1])
            xs += [x_coord, x_coord, x_coord + width, x_coord + width, x_coord]
            ys += [y, y + height, y + height, y, y]
        self.x = numpy.array(xs)
        self.y = numpy.array(ys)


class Diamond(Shape):
    def __init__(self, coords, y=0, height=0.25, **kwargs):
        super(Diamond, self).__init__(**kwargs)
        width = abs(coords[0][0] - coords[0][1])
        x_coord = min(coords[0][0], coords[0][1])
        hh = height / 2
        xs = [
            x_coord,
            x_coord + width / 2,
            x_coord + width,
            x_coord + width / 2,
            x_coord,
        ]
        ys = [y, y + hh, y, y - hh, y]
        for i in range(1, len(coords)):
            # Add coordinates for connecting line segment
            xs += [None, coords[i - 1][1], coords[i][0], None]
            ys += [None, y, y, None]
            # Add coordinates for individual diamond
            width = abs(coords[i][0] - coords[i][1])
            x_coord = min(coords[i][0], coords[i][1])
            xs += [
                x_coord,
                x_coord + width / 2,
                x_coord + width,
                x_coord + width / 2,
                x_coord,
            ]
            ys += [y, y + hh, y, y - hh, y]
        self.x = numpy.array(xs)
        self.y = numpy.array(ys)


class Arrow(Shape):
    def __init__(
        self, coords, y=0, height=0.25, arrow_head_w=0.1, reverse=False, **kwargs
    ):
        super(Arrow, self).__init__(**kwargs)
        xs = []
        ys = []
        for i in range(len(coords) - 1):
            # Add coordinates for individual rectangle
            width = abs(coords[i][0] - coords[i][1])
            x_coord = min(coords[i][0], coords[i][1])
            xs += [x_coord, x_coord, x_coord + width, x_coord + width, x_coord]
            ys += [y, y + height, y + height, y, y]
            # Add coordinates for connecting line segment
            xs += [None, coords[i][1], coords[i + 1][0], None]
            ys += [None, y + height / 2, y + height / 2, None]

        width = abs(coords[-1][0] - coords[-1][1])
        x_coord = min(coords[-1][0], coords[-1][1])
        hh = height * arrow_head_w * 2
        hw = width * arrow_head_w * 2

        # Coordinates for arrow head
        arrow_x = [
            x_coord,
            x_coord + width - hw,
            x_coord + width - hw,
            x_coord + width,
            x_coord + width - hw,
            x_coord + width - hw,
            x_coord,
            x_coord,
        ]
        arrow_y = [
            y,
            y,
            y - hh,
            y + height / 2,
            y + height + hh,
            y + height,
            y + height,
            y,
        ]
        if not reverse:
            xs += arrow_x
            ys += arrow_y
        else:
            arrow_x = numpy.array(arrow_x)
            arrow_y = numpy.array(arrow_y)
            xs += list(numpy.flip(arrow_x.max() - arrow_x + arrow_x.min()))
            ys += list(numpy.flip(arrow_y))

        self.x = numpy.array(xs)
        self.y = numpy.array(ys)


# https://plot.ly/python/marker-style/
# https://plot.ly/python/reference/#scatter-marker-symbol
class Point(Shape):
    _mode = "markers"

    def __init__(self, x, y, size=14, symbol="square", **kwargs):
        super(Point, self).__init__(**kwargs)
        self.x = numpy.array([x], dtype="O")
        self.y = numpy.array([y], dtype="O")
        self._size = size
        self._symbol = symbol


class _MakeShape:
    """container class that builds annotation shapes"""

    _colors = dict(
        cds="rgba(0,0,150,0.5)",
        exon="rgba(0,0,100,0.5)",
        gene="rgba(0,0,150,0.5)",
        transcript="rgba(0,0,200,0.5)",
        snp="rgba(200,0,0,0.5)",
        snv="rgba(200,0,0,0.5)",
    )
    _shapes = dict(
        cds=Arrow,
        exon=Arrow,
        transcript=Arrow,
        gene=Arrow,
        repeat=Rectangle,
        snp=Point,
        snv=Point,
        variation=Diamond,
    )

    def __call__(self, type_=None, name=None, coords=None, **kwargs):
        from cogent3.core.annotation import _Annotatable

        if isinstance(type_, _Annotatable):
            if not type_.map.useful:
                return None

            name = type_.name
            coords = type_.map.get_coordinates()
            reverse = type_.map.get_covering_span().reverse
            type_ = type_.type
        else:
            if coords[0][0] > coords[-1][1]:
                reverse = True
            else:
                reverse = False
            if coords is None:
                raise Exception("No coordinates defined")
        kwargs.update(dict(reverse=reverse))

        klass = self._shapes.get(type_.lower(), Rectangle)
        color = self._colors.get(type_.lower(), None)
        if klass != Arrow:
            kwargs.pop("reverse", None)

        if klass != Point:
            result = klass(
                name=type_,
                text=name,
                legendgroup=type_,
                coords=coords,
                fillcolor=color,
                **kwargs,
            )
        else:
            result = Point(
                name=type_,
                text=name,
                legendgroup=type_,
                x=min(coords[0][0], coords[-1][1]),
                y=1,
                size=14,
                symbol="square",
                fillcolor=color,
                **kwargs,
            )
        return result


make_shape = _MakeShape()