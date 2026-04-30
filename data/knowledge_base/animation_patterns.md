# Animation Patterns

Three tiers: implicit, explicit, Hero. Use the simplest one that does the job.

## 1. Implicit — animate properties over time

```dart
AnimatedContainer(
  duration: const Duration(milliseconds: 300),
  curve: Curves.easeInOut,
  width: expanded ? 300 : 100,
  decoration: BoxDecoration(
    color: expanded ? Colors.indigo : Colors.grey,
    borderRadius: BorderRadius.circular(expanded ? 20 : 8),
  ),
)
```

Other implicit widgets: `AnimatedOpacity`, `AnimatedPadding`, `AnimatedAlign`, `AnimatedSwitcher`, `AnimatedCrossFade`.

## 2. Explicit — full control via AnimationController

```dart
class _BouncingIconState extends State<BouncingIcon> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(
    duration: const Duration(milliseconds: 400),
    vsync: this,
  );
  late final Animation<double> _scale = Tween(begin: 1.0, end: 1.2)
      .animate(CurvedAnimation(parent: _c, curve: Curves.easeInOut));

  @override
  void dispose() { _c.dispose(); super.dispose(); }

  void _tap() async {
    await _c.forward();
    await _c.reverse();
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: _tap,
      child: ScaleTransition(scale: _scale, child: const Icon(Icons.favorite, size: 32)),
    );
  }
}
```

**Critical:** always `dispose()` controllers or you leak memory.

## 3. Hero — shared element across screens

```dart
// Source screen
Hero(tag: 'avatar_${user.id}', child: CircleAvatar(radius: 24));

// Destination screen
Hero(tag: 'avatar_${user.id}', child: CircleAvatar(radius: 80));
```

The tag must match on both sides and be unique per animated element.

## 4. Page transitions

With `go_router`:

```dart
GoRoute(
  path: '/details',
  pageBuilder: (context, state) => CustomTransitionPage(
    child: const DetailsScreen(),
    transitionsBuilder: (_, a, __, child) =>
        FadeTransition(opacity: a, child: child),
  ),
);
```

## Rules

- Default to implicit — `AnimatedContainer` beats a hand-rolled controller 9 times out of 10.
- Keep durations 200–400 ms for UI feedback, 500–800 ms for transitions.
- Always pick a `Curves` value — never linear.
- Dispose every controller.
