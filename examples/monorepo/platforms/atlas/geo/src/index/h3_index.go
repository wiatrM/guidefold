// Package index keeps PostGIS geometries and their H3 cell covers in sync.
//
// Every atlas geo layer stores a geometry column plus an h3_cells column at a
// fixed resolution declared in the layer manifest. These helpers are the only
// place that computes H3 cells, so the H3 library is upgraded in one spot.
package index

import (
	"errors"

	"github.com/twpayne/go-geom"
	"github.com/uber/h3-go/v4"
)

// MaxCellsPerRow caps the h3_cells array; larger covers must be compacted.
const MaxCellsPerRow = 2048

var (
	ErrTooManyCells = errors.New("index: geometry cover exceeds MaxCellsPerRow; use CompactCells")
	ErrUnsupported  = errors.New("index: unsupported geometry type")
)

// CellsForGeometry returns the H3 cells covering g at resolution res.
// Points yield exactly one cell; polygons yield their polyfill.
func CellsForGeometry(g geom.T, res int) ([]h3.Cell, error) {
	switch s := g.(type) {
	case *geom.Point:
		return []h3.Cell{h3.LatLngToCell(h3.LatLng{Lat: s.Y(), Lng: s.X()}, res)}, nil
	case *geom.Polygon:
		cells := h3.PolygonToCells(polygonToH3(s.Coords()), res)
		if len(cells) > MaxCellsPerRow {
			return nil, ErrTooManyCells
		}
		return cells, nil
	default:
		return nil, ErrUnsupported
	}
}

// CoverCells returns the cells for a bounding box, used as the cell-first
// filter (h3_cells && $1) before ST_ refinement in SQL.
func CoverCells(minLng, minLat, maxLng, maxLat float64, res int) []h3.Cell {
	ring := []geom.Coord{{minLng, minLat}, {maxLng, minLat}, {maxLng, maxLat}, {minLng, maxLat}, {minLng, minLat}}
	return h3.PolygonToCells(polygonToH3([][]geom.Coord{ring}), res)
}

// CompactCells collapses a cover into parent cells where a parent is fully covered.
func CompactCells(cells []h3.Cell) ([]h3.Cell, error) { return h3.CompactCells(cells) }

func polygonToH3(rings [][]geom.Coord) h3.GeoPolygon {
	var poly h3.GeoPolygon
	for i, ring := range rings {
		loop := make(h3.GeoLoop, 0, len(ring))
		for _, c := range ring {
			loop = append(loop, h3.LatLng{Lat: c.Y(), Lng: c.X()})
		}
		if i == 0 {
			poly.GeoLoop = loop
		} else {
			poly.Holes = append(poly.Holes, loop)
		}
	}
	return poly
}
