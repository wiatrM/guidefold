package main

import (
	"container/list"
	"sync"
)

// catalogCacheSize bounds how many immutable catalogs stay resident. One entry
// is one (tenant, repo, snapshot) triple; a new publication adds a key rather
// than mutating an existing one, so eviction is the only thing that removes a
// catalog and a request can never observe a half-built one.
const catalogCacheSize = 64

// catalogCache is a bounded LRU. It replaces the single cached catalog the
// store used to hold: with several organisations served by one process, a
// single slot would hand one tenant's cards to another on every alternating
// request. The key includes the snapshot id, so a rollback is a different
// entry rather than a stale one.
type catalogCache struct {
	mu    sync.Mutex
	max   int
	items map[string]*list.Element
	order *list.List // front = most recently used
}

type catalogEntry struct {
	key     string
	catalog *Catalog
}

func newCatalogCache(max int) *catalogCache {
	if max <= 0 {
		max = catalogCacheSize
	}
	return &catalogCache{max: max, items: map[string]*list.Element{}, order: list.New()}
}

func catalogKey(tenant, repo, snapshot string) string {
	return tenant + "\x00" + repo + "\x00" + snapshot
}

func (c *catalogCache) get(key string) *Catalog {
	c.mu.Lock()
	defer c.mu.Unlock()
	el, ok := c.items[key]
	if !ok {
		return nil
	}
	c.order.MoveToFront(el)
	return el.Value.(*catalogEntry).catalog
}

// put stores a catalog and returns the resident one for that key. Two requests
// that load the same snapshot concurrently therefore end up sharing a single
// instance, which matters because the dense path writes DensePrompt on it.
func (c *catalogCache) put(key string, catalog *Catalog) *Catalog {
	c.mu.Lock()
	defer c.mu.Unlock()
	if el, ok := c.items[key]; ok {
		c.order.MoveToFront(el)
		return el.Value.(*catalogEntry).catalog
	}
	c.items[key] = c.order.PushFront(&catalogEntry{key: key, catalog: catalog})
	for c.order.Len() > c.max {
		oldest := c.order.Back()
		if oldest == nil {
			break
		}
		c.order.Remove(oldest)
		delete(c.items, oldest.Value.(*catalogEntry).key)
	}
	return catalog
}

func (c *catalogCache) len() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.order.Len()
}
