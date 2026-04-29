# List & Grid Patterns

Most app screens show a collection of items. Use the right widget for each pattern.

## Lazy list (default choice)

```dart
ListView.builder(
  itemCount: items.length,
  itemBuilder: (context, i) => PostCard(post: items[i]),
)
```

`ListView.builder` only builds items near the viewport — use it for any list over 20 items. Never use the plain `ListView(children: [...])` with a mapped list of 50+ items; it builds all of them upfront.

## Separated list

```dart
ListView.separated(
  itemCount: items.length,
  separatorBuilder: (_, __) => const Divider(height: 1),
  itemBuilder: (_, i) => ListTile(title: Text(items[i].name)),
)
```

## Grid

```dart
GridView.builder(
  padding: const EdgeInsets.all(12),
  gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
    crossAxisCount: 2,
    crossAxisSpacing: 12,
    mainAxisSpacing: 12,
    childAspectRatio: 0.75,
  ),
  itemCount: products.length,
  itemBuilder: (_, i) => ProductCard(product: products[i]),
)
```

Use `SliverGridDelegateWithMaxCrossAxisExtent` when you want responsive column count (tablet gets more columns automatically).

## Pull to refresh

```dart
RefreshIndicator(
  onRefresh: () => context.read<PostBloc>().reload(),
  child: ListView.builder(...),
)
```

## Infinite scroll

Detect when user reaches the end via a `ScrollController`:

```dart
final _controller = ScrollController();
_controller.addListener(() {
  if (_controller.position.pixels >= _controller.position.maxScrollExtent - 200) {
    context.read<PostBloc>().add(LoadMorePosts());
  }
});
```

## Empty state

Always show something when the list is empty:

```dart
if (items.isEmpty) {
  return const Center(child: Text('Nothing here yet'));
}
```

## Rules

- Always `const` the gridDelegate when fields don't change.
- Wrap tap-able list items in `InkWell` or `ListTile` for the ripple.
- Never build ~50+ items into a non-builder list.
