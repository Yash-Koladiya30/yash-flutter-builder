# Responsive Layout

AppAspect apps run on phones (primary), tablets, and occasionally foldables. Use breakpoints, not fixed widths.

## Breakpoints

```dart
class Breakpoints {
  static const mobile = 600.0;
  static const tablet = 1024.0;
  // Anything above 1024 = desktop/large-tablet
}
```

## Simple responsive widget

```dart
class Responsive extends StatelessWidget {
  final Widget mobile;
  final Widget? tablet;
  final Widget? desktop;

  const Responsive({super.key, required this.mobile, this.tablet, this.desktop});

  @override
  Widget build(BuildContext context) {
    final w = MediaQuery.sizeOf(context).width;
    if (w >= Breakpoints.tablet && desktop != null) return desktop!;
    if (w >= Breakpoints.mobile && tablet != null) return tablet!;
    return mobile;
  }
}
```

Usage:

```dart
Responsive(
  mobile: PostList(),
  tablet: Row(children: [PostList(), PostDetail()]),
)
```

## LayoutBuilder for sub-layouts

When only a part of the screen should adapt, use `LayoutBuilder`:

```dart
LayoutBuilder(builder: (context, constraints) {
  final cols = constraints.maxWidth ~/ 180;
  return GridView.count(crossAxisCount: cols, children: [...]);
});
```

## SafeArea

Always wrap root screen content in `SafeArea` to respect notches and home indicators:

```dart
Scaffold(body: SafeArea(child: ...))
```

Scaffolds add SafeArea automatically to the body, but nested screens and custom scaffolds may not — add it explicitly.

## Rules

- Never hardcode widths like `width: 375` — it breaks on every other device.
- Use `MediaQuery.sizeOf(context)` (sized-only dependency) over `MediaQuery.of(context).size` (full rebuild dependency).
- Test both portrait and landscape before shipping.
- Use `AspectRatio` to keep card proportions consistent across sizes.
