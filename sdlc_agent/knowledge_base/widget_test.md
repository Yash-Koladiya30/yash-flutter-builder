# Widget Test Template

Every screen in an AppAspect app has a matching widget test at `test/<screen>_test.dart`.

## Template

```dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:my_app/screens/home_screen.dart';

void main() {
  group('HomeScreen', () {
    testWidgets('renders without error', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(home: HomeScreen()),
      );
      expect(find.byType(HomeScreen), findsOneWidget);
    });

    testWidgets('displays app bar', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(home: HomeScreen()),
      );
      expect(find.byType(AppBar), findsOneWidget);
    });
  });
}
```

## Rules

- Always wrap the screen in `MaterialApp` — prevents missing `Directionality` errors.
- Use `find.byType(...)` rather than `find.text(...)` for structural checks.
- Never use `Timer.run` or real delays in tests — use `pumpAndSettle()`.
- Prefer `group(...)` blocks — lets you organise tests per feature.
