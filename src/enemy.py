import pygame


class Enemy:
    _next_id = 0

    def __init__(self, world_x, y, move_range=100, speed=2, width=40, height=40, scale=1.0, use_gravity=True,
                 stomp_kills_enemy=True, touch_kills_player=True, bounce_on_stomp=True):
        """
        world_x: 世界座標でのx
        y      : 画面上でのy（地面にいる感じ）
        move_range: 中心から左右にどれくらい動くか
        speed  : 左右の移動速度
        use_gravity: 重力を適用するかどうか
        stomp_kills_enemy: 踏むと敵を倒すか
        touch_kills_player: 触れるとプレイヤーが死ぬか
        bounce_on_stomp: 踏んだ時にバウンスするか
        """
        self.id = Enemy._next_id
        Enemy._next_id += 1
        self.center_x = world_x
        self.world_x = world_x
        self.y = y
        self.move_range = move_range
        self.speed = speed
        self.width = width
        self.height = height
        self.base_width = width
        self.base_height = height
        self.scale = 1.0
        self.direction = 1  # 1:右へ, -1:左へ
        self.color = (255, 80, 80)
        self.use_gravity = use_gravity
        self.vx = 0  # x方向の速度（API制御用）
        self.vy = 0  # y方向の速度
        self.use_api_control = False  # APIからの制御を使うかどうか
        
        # 衝突判定設定
        self.stomp_kills_enemy = stomp_kills_enemy
        self.touch_kills_player = touch_kills_player
        self.bounce_on_stomp = bounce_on_stomp
        
        # Load images
        self.images = []
        self.source_images = []
        self.use_image = False
        try:
            for i in range(1, 5):
                img = pygame.image.load(f'assets/enemy/{i}.png').convert_alpha()
                self.source_images.append(img)
            self.use_image = True
        except Exception as e:
            print(f"Failed to load enemy images: {e}")
            self.use_image = False

        # Set initial scale
        self.set_scale(scale)

        # Animation state
        self.animation_timer = 0
        self.current_frame_index = 0
        self.ANIMATION_SPEED = 6  # 24 frames / 4 images = 6 frames per image

    def _refresh_images(self):
        if not self.source_images:
            return

        scaled_width = max(1, int(self.width * 1.2))
        scaled_height = max(1, int(self.height * 1.2))
        self.images = [
            pygame.transform.scale(img, (scaled_width, scaled_height))
            for img in self.source_images
        ]

    def set_scale(self, scale):
        safe_scale = max(0.25, min(float(scale), 4.0))
        prev_bottom = self.y

        self.scale = safe_scale
        self.width = max(4, int(round(self.base_width * safe_scale)))
        self.height = max(4, int(round(self.base_height * safe_scale)))
        if self.source_images:
            self._refresh_images()

        # Keep feet anchored
        self.y = prev_bottom

    def move_patrol(self):
        """左右に往復運動"""
        self.world_x += self.speed * self.direction
        if self.world_x > self.center_x + self.move_range:
            self.world_x = self.center_x + self.move_range
            self.direction *= -1
        elif self.world_x < self.center_x - self.move_range:
            self.world_x = self.center_x - self.move_range
            self.direction *= -1

    def update(self, platforms, ground_y, gravity, is_on_ground_func=None):
        # 移動処理
        if self.use_api_control:
            # APIから速度が設定されている場合
            self.world_x += self.vx
            # API制御の場合もY方向の速度は重力で制御される
            # （vyがAPIで設定されても重力が上書きする）
        else:
            # 通常の往復運動
            self.move_patrol()
        
        # 重力を適用
        if self.use_gravity:
            self.vy += gravity
            self.y += self.vy
            
            # 地面判定（崖でない場所のみ）
            if self.y >= ground_y and self.vy > 0:
                # is_on_ground_func が提供されている場合は崖判定を行う
                if is_on_ground_func is None or is_on_ground_func(self.world_x):
                    self.y = ground_y
                    self.vy = 0
                # 崖の場合は着地しない（落下し続ける）
            
            # 段差との判定
            enemy_rect_world = pygame.Rect(
                self.world_x - self.width // 2,
                self.y - self.height,
                self.width,
                self.height
            )
            
            for platform in platforms:
                platform_rect_world = pygame.Rect(
                    platform.world_x,
                    platform.y,
                    platform.width,
                    platform.height
                )
                
                if enemy_rect_world.colliderect(platform_rect_world):
                    # 上から乗った場合
                    if self.vy > 0 and enemy_rect_world.bottom <= platform_rect_world.top + 10:
                        self.y = platform_rect_world.top
                        self.vy = 0

    def draw(self, surface, camera_x):
        # world_x を camera_x でずらして画面上の位置に変換
        screen_x = int(self.world_x - camera_x)
        
        if self.use_image and self.images:
            # Update animation
            self.animation_timer += 1
            if self.animation_timer >= self.ANIMATION_SPEED:
                self.animation_timer = 0
                self.current_frame_index = (self.current_frame_index + 1) % len(self.images)
            
            current_img = self.images[self.current_frame_index]

            # 画像を描画
            image_width = current_img.get_width()
            image_height = current_img.get_height()
            image_x = screen_x - image_width // 2
            image_y = self.y - image_height  # 足元を基準に
            
            # 向きに応じて反転
            # 画像は左向き(direction=-1)がデフォルト
            if self.direction == 1:
                # 右向きに移動中 -> 反転して右を向かせる
                flipped_image = pygame.transform.flip(current_img, True, False)
                surface.blit(flipped_image, (image_x, image_y))
            else:
                # 左向きに移動中 -> そのまま描画
                surface.blit(current_img, (image_x, image_y))
        else:
            # フォールバック: 矩形描画
            rect = pygame.Rect(screen_x - self.width // 2,
                               self.y - self.height,
                               self.width, self.height)
            pygame.draw.rect(surface, self.color, rect)

    def get_rect(self, camera_x):
        """当たり判定用の矩形を返す"""
        screen_x = int(self.world_x - camera_x)
        return pygame.Rect(screen_x - self.width // 2,
                          self.y - self.height,
                          self.width, self.height)
