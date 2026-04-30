# Flutter Project Structure

Standard layout for every Flutter app. Files under `lib/` only.

```
my_app/
├── pubspec.yaml          — dependencies, assets, metadata
├── lib/
│   ├── main.dart         — entry point + MaterialApp.router + BlocProviders
│   ├── models/           — data classes (Post, User, Receipt, ...)
│   │   ├── post.dart
│   │   └── user.dart
│   ├── blocs/            — flutter_bloc files (one bloc per feature)
│   │   ├── auth_bloc.dart
│   │   ├── post_bloc.dart
│   │   └── ...
│   ├── screens/          — Scaffold-level widgets
│   │   ├── home_screen.dart
│   │   ├── login_screen.dart
│   │   └── ...
│   ├── widgets/          — reusable sub-widgets (cards, tiles, dialogs)
│   ├── repositories/     — data access layer (API, Hive)
│   ├── theme/            — AppTheme + design tokens
│   └── router.dart       — go_router config
└── test/                 — flutter_test files (one per screen/bloc)
    ├── home_screen_test.dart
    └── auth_bloc_test.dart
```

## Naming conventions

- **Files:** `snake_case.dart` — `user_profile_screen.dart`, not `UserProfileScreen.dart`.
- **Classes:** `PascalCase` — `UserProfileScreen`, `AuthBloc`, `PostRepository`.
- **Screens** end in `Screen`: `HomeScreen`, `SettingsScreen`.
- **BLoCs** end in `Bloc`: `AuthBloc`, `PostBloc`.
- **Repositories** end in `Repository`: `PostRepository`.

## Import rules

- Use `package:my_app/...` imports, never relative `../../`.
- Keep Flutter SDK imports first, then package imports, then relative imports (rare).

```dart
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:my_app/models/post.dart';
import 'package:my_app/blocs/post_bloc.dart';
```

## One widget per file

Each screen gets its own file. Small private sub-widgets (`_PostCard`, `_ErrorView`) can sit in the same file with a leading underscore.
