<a class="social" href="<?php echo esc_url( $url ); ?>" target="_blank" rel="noopener">
  <svg class="icon" aria-hidden="true"><use href="#it-facebook"></use></svg>
  <span class="visually-hidden"><?php echo esc_html( $name ); ?></span>
</a>
<label for="search" class="visually-hidden"><?php esc_html_e( 'Cerca', 'theme' ); ?></label>
<input id="search" type="search" name="s" />
<a class="tag" href="<?php echo esc_url( $tag ); ?>">#<?php echo esc_html( $t->name ); ?></a>
