import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.patches import Circle
import numpy as np



def main():
    # Tạo dữ liệu cho đồ thị 3D
    num_nodes = 5
    initial_positions = np.random.rand(num_nodes, 3) * 100
    initial_velocities = np.random.uniform(-5, 5, size=(5, 3))

    # Tạo một đối tượng subplot 3D
    fig = plt.figure(figsize=(16, 9))
    ax = fig.add_subplot(111, projection='3d')

    # Vẽ các điểm trên đồ thị 3D
    nodes = ax.scatter(initial_positions[:, 0], initial_positions[:, 1], initial_positions[:, 2], color='b')

    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.set_zlim(0, 100)
    # Đặt nhãn cho các trục
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('Z')


    # Cập nhật vị trí các node trong mỗi bước thời gian
    for t in range(100):
        plt.cla()
        initial_positions += initial_velocities * 0.1
        nodes._offsets3d = (initial_positions[:, 0], initial_positions[:, 1], initial_positions[:, 2])
        x, y, z = np.reshape(nodes._offsets3d, (3, num_nodes))
        ax.scatter(x, y, z, color='b')
        ax.plot3D(x[:1], y[:1], z[:1], color='r')
        plt.draw()
        for idx in range(num_nodes):
            change_velocity = np.random.uniform(0, 1) < 0.1
            if change_velocity:
                initial_velocities[idx] = np.random.uniform(-1, 1, size=(1, 3))
        plt.pause(0.1)

    # Hiển thị đồ thị 3D
    plt.show()

if __name__ == '__main__':
    main()